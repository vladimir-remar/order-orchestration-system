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
with a different payload, the endpoint returns HTTP 409 (conflict).
"""
import httpx
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .schemas import CreateOrderDTO
from .domain import Order, OrderItem

from .providers import get_order_service
from .repository import OrderRepository
from .idempotency import get_or_create_idempotent, finalize

class OrdersPingView(APIView):
    """Simple health-check endpoint for the orders module.

    This view returns a minimal JSON payload used by liveness/health
    checks and by automated smoke-tests.
    """

    def get(self, request):
        """Handle GET requests for the health endpoint.

        Returns:
            Response: A DRF Response with JSON {"ok": True} and HTTP 200.
        """
        return Response({"ok": True})


class CreateOrderView(APIView):
    """Endpoint to create new orders.

    This view expects a JSON payload matching `CreateOrderDTO`. It
    validates the input with Pydantic, maps the input DTO to domain
    objects, invokes the domain `OrderService` and returns an appropriate
    HTTP response based on the domain outcome.

    The default wiring uses HTTP adapter clients to call external
    inventory/payments services; network or upstream errors are mapped to
    a 503 to indicate temporary unavailability.
    """

    def post(self, request):
        """Handle POST requests to create an order.

        Behavior:
            1. Read optional ``Idempotency-Key`` header.
            2. Validate incoming JSON using ``CreateOrderDTO``.
            3. If idempotency is enabled: get-or-create a record.
               - If existing with same payload: return stored body (200).
               - If existing with different payload: return 409 conflict.
            4. Map validated DTO to domain ``Order`` and ``OrderItem``.
            5. Invoke the domain ``OrderService`` obtained from
               ``get_order_service()``.
            6. Translate domain errors into HTTP responses:
               - ``INSUFFICIENT_STOCK`` -> 422
               - ``PAYMENT_FAILED`` -> 402
               - other domain errors -> 400
               Persist idempotent response when applicable.
            7. Persist the order and return 201 with ``{"id", "status"}``.
               Persist idempotent response when applicable.

        Args:
            request: DRF Request instance containing JSON payload.

        Returns:
            Response: On success, 201 with the order id and status.
            On validation, domain, or transport errors returns an
            appropriate 4xx/5xx response. When idempotency is used,
            cached responses are returned with 200 on retries or 409 on
            payload conflict.
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
                return Response(rec.response_body, status=200)

        # 3) Domain
        items = [OrderItem(sku=i.sku, quantity=i.quantity) for i in dto.items]
        order = Order(id=None, items=items, total_cents=dto.amount_cents, currency=dto.currency)
        service = get_order_service()
        try:
            out = service.place_order(order)
        except ValueError as e:
            code = str(e)
            status_code = 422 if code == "INSUFFICIENT_STOCK" else (402 if code == "PAYMENT_FAILED" else 400)
            body = {"detail": code}
            if rec: finalize(rec, status_code, body)
            return Response(body, status=status_code)
        except Exception:
            body = {"detail": "UPSTREAM_UNAVAILABLE"}
            if rec: finalize(rec, 503, body)
            return Response(body, status=503)

        # 4) Persistence + response
        repo = OrderRepository()
        new_id = repo.create(out)
        body = {"id": str(new_id), "status": out.status.value}
        if rec: finalize(rec, 201, body, order_id=new_id)
        return Response(body, status=201)