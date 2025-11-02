"""Service provider helpers for wiring OrderService with ports.

This module exposes a small factory function `get_order_service` that
returns a configured `OrderService` instance. By default it will try to
use the HTTP adapter clients (if available and enabled via
settings.USE_HTTP_ADAPTERS). When the HTTP adapters are not available
or disabled, the function falls back to fast in-process stubs suitable
for tests and local development.
"""

from django.conf import settings
from .domain import OrderService
from .adapters import InventoryStub, PaymentsStub


try:
    from .http_adapters import HttpInventoryClient, HttpPaymentsClient
except ImportError:
    # If httpx (or other HTTP dependencies) are not available in the
    # current environment, make the HTTP clients None so the provider
    # falls back to the lightweight stub implementations.
    HttpInventoryClient = HttpPaymentsClient = None  # type: ignore


def get_order_service() -> OrderService:
    """Return a configured OrderService instance.

    If `settings.USE_HTTP_ADAPTERS` is truthy and the HTTP adapter
    clients are importable, the returned service will use the HTTP
    implementations to call external services. Otherwise the function
    returns an OrderService wired with in-memory stub adapters.

    Returns:
        OrderService: A service instance with appropriate ports.
    """
    if getattr(settings, "USE_HTTP_ADAPTERS", True) and HttpInventoryClient and HttpPaymentsClient:
        return OrderService(
            inventory=HttpInventoryClient(),
            payments=HttpPaymentsClient(),
        )

    # Fallback to stubs (tests or environments without HTTP dependencies)
    return OrderService(
        inventory=InventoryStub(),
        payments=PaymentsStub(),
    )
