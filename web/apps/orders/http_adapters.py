"""HTTP adapter clients for external services used by the orders domain.

This module provides concrete implementations of the domain ports
(``InventoryPort`` and ``PaymentsPort``) that communicate with external
microservices over HTTP using ``httpx``. The implementations are thin
wrappers that translate domain objects to JSON payloads and interpret
the responses.
"""

import uuid
from typing import List, Optional
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

        Args:
            items: List of ``OrderItem`` to reserve.

        Returns:
            bool: True if the external service reports the items were
            reserved; False if reservation failed (for example, when the
            service returns 422 insufficient stock).

        Raises:
            httpx.RequestError: On network or transport errors.
            httpx.HTTPStatusError: On non-2xx responses not explicitly
                handled (after ``raise_for_status()``).
        """
        payload = {"items": [{"sku": i.sku, "quantity": i.quantity} for i in items]}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/reserve", json=payload)
            if r.status_code == 200:
                return bool(r.json().get("reserved", False))
            if r.status_code == 422:
                return False
            r.raise_for_status()
            return False

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

    def charge(self, amount_cents: int, currency: str) -> tuple[bool, Optional[uuid.UUID]]:
        """Charge the specified amount using the payments service.

        Args:
            amount_cents: Amount to charge expressed in integer cents.
            currency: ISO currency code (e.g., "EUR").

        Returns:
            tuple[bool, Optional[uuid.UUID]]: ``(paid, transaction_id)``
            where ``paid`` is True when the charge succeeds and
            ``transaction_id`` is the UUID of the created transaction (or
            None when the charge fails or no id is provided).

        Raises:
            httpx.RequestError: On network or transport errors.
            httpx.HTTPStatusError: On non-2xx responses not explicitly
                handled (after ``raise_for_status()``).

        Notes:
            A 402 Payment Required response is treated as an expected
            negative outcome and returns ``(False, None)`` without raising.
        """
        payload = {"amount_cents": amount_cents, "currency": currency}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/charge", json=payload)
            if r.status_code == 200:
                data = r.json()
                tx = data.get("transaction_id")
                return True, (uuid.UUID(tx) if tx else None)
            if r.status_code == 402:
                return False, None
            r.raise_for_status()
            return False, None
