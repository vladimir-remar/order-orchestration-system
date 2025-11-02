"""HTTP views for the orders app.

This module contains DRF API views used by the orders service. Views are
kept intentionally small: they validate requests (via Pydantic), map to
domain DTOs, delegate to the domain service, and return an HTTP response.

The views obtain a configured `OrderService` from the `get_order_service()`
provider which will either return HTTP adapter-backed ports
(`HttpInventoryClient`, `HttpPaymentsClient`) or in-process stubs
(`InventoryStub`, `PaymentsStub`) depending on runtime settings. This
allows tests and local development to swap implementations without
changing view logic.
"""
import httpx
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .schemas import CreateOrderDTO
from .domain import Order, OrderItem

from .providers import get_order_service

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

        Behaviour:
            1. Validate incoming JSON using `CreateOrderDTO`.
            2. Map validated DTO to domain `Order` and `OrderItem`.
                3. Invoke the domain `OrderService` obtained from
                    `get_order_service()` (which selects HTTP adapters or
                    stubs based on configuration).
            4. Translate domain and transport errors into HTTP responses.

        Args:
            request: DRF Request instance containing JSON payload.

        Returns:
            DRF Response object. On success returns 201 with the order
            status. On validation, domain, or transport errors returns an
            appropriate 4xx/5xx response.
        """
        # 1) Validation with Pydantic
        try:
            dto = CreateOrderDTO.model_validate(request.data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        items = [OrderItem(sku=i.sku, quantity=i.quantity) for i in dto.items]
        order = Order(id=None, items=items, total_cents=dto.amount_cents, currency=dto.currency)

        service = get_order_service() 

        try:
            out = service.place_order(order)
        except ValueError as e:
            code = str(e)
            if code == "INSUFFICIENT_STOCK":
                return Response({"detail": code}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            if code == "PAYMENT_FAILED":
                return Response({"detail": code}, status=status.HTTP_402_PAYMENT_REQUIRED)
            return Response({"detail": code}, status=status.HTTP_400_BAD_REQUEST)
        except httpx.HTTPError:
            # Errores de red: dependencia externa caída → 502/503 (elige política)
            return Response({"detail": "UPSTREAM_UNAVAILABLE"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({"status": out.status.value}, status=status.HTTP_201_CREATED)