"""HTTP views for the orders app.

This module contains DRF API views used by the orders service. Views are
kept intentionally small: they validate requests (via Pydantic), map to
domain DTOs, delegate to the domain service, and return an HTTP response.

The views obtain a configured ``OrderService`` from ``get_order_service()``
which returns HTTP adapter-backed ports (``HttpInventoryClient``,
``HttpPaymentsClient``) or in-process stubs (``InventoryStub``,
``PaymentsStub``) depending on runtime settings. This allows tests and
local development to swap implementations without changing view logic.

Idempotency: when an ``Idempotency-Key`` header is provided, the create
endpoint ensures idempotent processing. The first request creates a record
and, upon completion, stores the response. Subsequent retries with the same
payload return the stored response with HTTP 200. If the same key is reused
with a different payload, the endpoint returns HTTP 409 (conflict). When HTTP
adapters are enabled, the key is also propagated to the payments HTTP client
to enable end-to-end idempotency across services.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .schemas import CreateOrderDTO
from .domain import Order, OrderItem

from .repository import OrderRepository
from .idempotency import get_or_create_idempotent, finalize
from .providers import get_order_service
from .http_adapters import HttpPaymentsClient
from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404
from .models import OrderModel
from .schemas import OrderReadDTO
from rest_framework.throttling import ScopedRateThrottle


class OrdersPingView(APIView):
    """Simple health-check endpoint for the orders module.

    This view returns a minimal JSON payload used by liveness/health
    checks and by automated smoke-tests.
    """

    def get(self, request):
        """Handle GET requests for the health endpoint.

        Args:
            request (Request): The incoming DRF request.

        Returns:
            Response: A DRF Response with JSON {"ok": True} and HTTP 200.
        """
        return Response({"ok": True})


class OrdersCollectionView(APIView):
    """Create an order by orchestrating inventory and payment.

    This view validates the payload using a Pydantic DTO, calls the domain
    service to reserve stock and charge the payment, persists the order, and
    returns the created resource. It supports idempotency via the
    ``Idempotency-Key`` header: the first request is processed and its
    response cached; subsequent retries with the same key and identical
    payload return the cached response with HTTP 200. Reusing the same key
    with a different payload returns HTTP 409.
    """
    throttle_classes = [ScopedRateThrottle]
    
    def get_throttles(self):
        # DRF evalúa los throttles en initial(), antes de get/post
        self.throttle_scope = "orders_list" if self.request.method == "GET" else "orders_create"
        return [throttle() for throttle in self.throttle_classes]
    
    def get(self, request):
        
        qs = OrderModel.objects.order_by("-created_at")
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        p = Paginator(qs, page_size)
        page_obj = p.get_page(page)

        results = []
        for o in page_obj.object_list:
            dto = OrderReadDTO(
                id=o.id,
                status=o.status,
                amount_cents=o.total_cents,   # <- clave
                currency=o.currency,
                transaction_id=o.transaction_id,
            )
            results.append(dto.model_dump(exclude_none=True))

        return Response(
            {
                "count": p.count,
                "page": page_obj.number,
                "page_size": page_size,
                "results": results,
            },
            status=200,
        )

    def post(self, request):
        """Create a new order.

        Args:
            request (Request): DRF request with JSON body and optional
                ``Idempotency-Key`` header.

        Returns:
                        Response: One of the following responses.
            - 201 with {id, status, transaction_id} when the order is created.
            - 200 with cached body when the same idempotency key and payload
              are retried.
            - 409 with {detail: "IDEMPOTENCY_CONFLICT"} when the same key is
              reused with a different payload.
            - 400 for DTO validation errors.
            - 422 with {detail: "INSUFFICIENT_STOCK"} when stock cannot be
              reserved.
            - 402 with {detail: "PAYMENT_FAILED"} when the payment is
              declined.
            - 503 with {detail: "UPSTREAM_UNAVAILABLE"} when upstream
              services are unavailable.
        """
        idem_key = request.headers.get("Idempotency-Key")

        # 1) Pydantic validation
        try:
            dto = CreateOrderDTO.model_validate(request.data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Idempotency get-or-create
        rec = None
        if idem_key:
            try:
                existing, rec = get_or_create_idempotent(idem_key, request.data)
            except ValueError:
                return Response({"detail": "IDEMPOTENCY_CONFLICT"}, status=status.HTTP_409_CONFLICT)
            if existing:
                # return Response(rec.response_body, status=200)
                status_code = rec.response_status or status.HTTP_200_OK
                resp = Response(rec.response_body, status=status_code)
                resp["Idempotent-Replay"] = "true"
                return resp

        # 3) Domain
        items = [OrderItem(sku=i.sku, quantity=i.quantity) for i in dto.items]
        order = Order(id=None, items=items, total_cents=dto.amount_cents, currency=dto.currency)
        service = get_order_service()
        # If using HTTP adapters and an Idempotency-Key is present, inject it into the Payments client

        try:
            if getattr(settings, "USE_HTTP_ADAPTERS", False) and idem_key:
                # get_order_service returns a service instance with HttpPaymentsClient
                # Set the "_idem_key" attribute if present
                payments = getattr(service, "payments", None)
                if isinstance(payments, HttpPaymentsClient):
                    payments._idem_key = idem_key
        except Exception:
            pass

        try:
            out = service.place_order(order)
        except ValueError as e:
            code = str(e)
            status_code = 422 if code == "INSUFFICIENT_STOCK" else (402 if code == "PAYMENT_FAILED" else 400)
            body = {"detail": code}
            if rec:
                finalize(rec, status_code, body)
            return Response(body, status=status_code)
        except Exception:
            body = {"detail": "UPSTREAM_UNAVAILABLE"}
            if rec:
                finalize(rec, 503, body)
            return Response(body, status=503)

        # 4) Persistence + response
        repo = OrderRepository()
        new_id = repo.create(out)
        body = {
            "id": str(new_id),
            "status": out.status.value,
            "transaction_id": (str(out.transaction_id) if out.transaction_id else None),
        }

        if rec:
            finalize(rec, status.HTTP_201_CREATED, body, order_id=new_id)
            return Response(body, status=status.HTTP_201_CREATED)

        return Response(body, status=status.HTTP_201_CREATED)
    
class RetrieveOrderView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "orders_detail"

    def get(self, request, oid: str):
        try:
            o = OrderModel.objects.get(id=oid)
        except OrderModel.DoesNotExist:
            return Response({"detail": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)

        dto = OrderReadDTO.model_validate({
            "id": str(o.id),
            "status": o.status,
            "amount_cents": o.total_cents,
            "currency": o.currency,
            "transaction_id": (str(o.transaction_id) if o.transaction_id else None),
        })
        return Response(dto.model_dump(by_alias=True, exclude_none=True), status=200)
