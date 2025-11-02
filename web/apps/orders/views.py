"""HTTP views for the orders app.

This module contains DRF API views used by the orders service. Views are
kept intentionally small: they perform request validation (via Pydantic),
map to domain DTOs, delegate to the domain service, and return an HTTP
response. The implementations below use local stub adapters for inventory
and payments in development and tests.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .schemas import CreateOrderDTO
from .domain import OrderService, Order, OrderItem
from .adapters import InventoryStub, PaymentsStub


class OrdersPingView(APIView):
    """Simple health-check endpoint for the orders module.

    This view returns a minimal JSON payload used by liveness/health checks
    and by automated smoke-tests.
    """

    def get(self, request):
        """Handle GET requests for the health endpoint.

        Returns:
            Response: A DRF Response with JSON {"ok": True} and HTTP 200.
        """
        return Response({"ok": True})


class CreateOrderView(APIView):
    """Endpoint to create new orders.

    This view expects a JSON payload matching `CreateOrderDTO`. It validates
    the input with Pydantic, maps the input DTO to domain objects, invokes
    the domain `OrderService`, and returns an appropriate HTTP response
    based on the domain outcome.
    """

    def post(self, request):
        """Handle POST requests to create an order.

        Behaviour:
            1. Validate incoming JSON using `CreateOrderDTO`.
            2. Map validated DTO to domain `Order` and `OrderItem`.
            3. Use `OrderService` (with local stubs) to place the order.
            4. Translate domain errors into HTTP responses.

        Args:
            request: DRF Request instance containing JSON payload.

        Returns:
            DRF Response object. On success returns 201 with the order
            status. On validation or domain errors returns an appropriate
            4xx/5xx response.
        """
        # 1) Validation with Pydantic
        try:
            dto = CreateOrderDTO.model_validate(request.data)
        except Exception as e:
            # Pydantic raises ValidationError with structured data; return 400
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Map to domain DTOs (Order/OrderItem)
        items = [OrderItem(sku=i.sku, quantity=i.quantity) for i in dto.items]
        order = Order(id=None, items=items, total_cents=dto.amount_cents, currency=dto.currency)

        # 3) Domain service with ports (stubs for now)
        service = OrderService(InventoryStub(), PaymentsStub())

        try:
            out = service.place_order(order)
        except ValueError as e:
            code = str(e)
            if code == "INSUFFICIENT_STOCK":
                return Response({"detail": code}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            if code == "PAYMENT_FAILED":
                return Response({"detail": code}, status=status.HTTP_402_PAYMENT_REQUIRED)
            return Response({"detail": code}, status=status.HTTP_400_BAD_REQUEST)

        # 4) Response (no persistence yet)
        return Response({"status": out.status.value}, status=status.HTTP_201_CREATED)