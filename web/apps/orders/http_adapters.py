"""HTTP adapter clients for external services used by the orders domain.

This module provides concrete implementations of the domain ports
(`InventoryPort` and `PaymentsPort`) that communicate with external
microservices over HTTP using `httpx`. The implementations are thin
wrappers that translate domain objects to JSON payloads and interpret
the responses.
"""

from typing import List
import httpx
from django.conf import settings
from .domain import InventoryPort, PaymentsPort, OrderItem


class HttpInventoryClient(InventoryPort):
    """HTTP client for the inventory service implementing InventoryPort.

    Attributes:
        base_url: Base URL of the inventory service. Defaults to
            `settings.INVENTORY_BASE_URL` when not provided.
        timeout: Request timeout in seconds. Defaults to
            `settings.HTTP_TIMEOUT_SECS` when not provided.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.INVENTORY_BASE_URL
        self.timeout = timeout or settings.HTTP_TIMEOUT_SECS

    def reserve(self, items: List[OrderItem]) -> bool:
        """Attempt to reserve the given list of order items.

        The method sends a POST request to the inventory service and
        returns True when the response indicates the reservation was
        successful.

        Args:
            items: List of OrderItem objects to reserve.

        Returns:
            True if the external service reports the items were reserved,
            False otherwise.

        Raises:
            httpx.HTTPError: For transport-level or non-2xx responses.

        Notes:
            A 422 Unprocessable Entity response (insufficient stock)
            is treated as a valid negative outcome and returns False
            without raising an exception.
        """
        payload = {"items": [{"sku": i.sku, "quantity": i.quantity} for i in items]}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/reserve", json=payload)
            if r.status_code == 200:
                data = r.json()
                return bool(data.get("reserved", False))
            if r.status_code == 422:
                # Insufficient stock -> reservation failed; do not raise
                return False
            # Any other non-2xx code is unexpected -> raise
            r.raise_for_status()
            return False  # por tipo

class HttpPaymentsClient(PaymentsPort):
    """HTTP client for the payments service implementing PaymentsPort.

    Attributes:
        base_url: Base URL of the payments service, defaults to
            `settings.PAYMENTS_BASE_URL`.
        timeout: Request timeout in seconds, defaults to
            `settings.HTTP_TIMEOUT_SECS`.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.PAYMENTS_BASE_URL
        self.timeout = timeout or settings.HTTP_TIMEOUT_SECS

    def charge(self, amount_cents: int, currency: str) -> bool:
        """Charge the specified amount using the payments service.

        Args:
            amount_cents: Amount to charge expressed in integer cents.
            currency: ISO currency code (e.g. 'EUR').

        Returns:
            True if the external service reports the payment succeeded,
            False otherwise.

        Raises:
            httpx.HTTPError: For transport-level or non-2xx responses.

        Notes:
            A 402 Payment Required response (payment failed) is treated
            as a valid negative outcome and returns False without
            raising an exception.
        """
        payload = {"amount_cents": amount_cents, "currency": currency}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/charge", json=payload)
            if r.status_code == 200:
                data = r.json()
                return bool(data.get("paid", False))
            if r.status_code == 402:
                # Payment declined -> return False; do not raise
                return False
            r.raise_for_status()
            return False
