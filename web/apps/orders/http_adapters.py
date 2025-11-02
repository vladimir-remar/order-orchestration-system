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
from django.utils.module_loading import import_string
from .domain import InventoryPort, PaymentsPort, OrderItem

REQUEST_ID_CTX = import_string("gateway.middleware.REQUEST_ID_CTX")


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
        """Attempt to charge a payment via the payments service.

        The request body includes ``amount_cents`` and ``currency``. If the
        instance has an ``_idem_key`` attribute (set by the view), an
        ``Idempotency-Key`` header is propagated to enable end-to-end
        idempotency in the payments service.

        Args:
            amount_cents: Payment amount in minor currency units (cents).
            currency: Three-letter ISO currency code (e.g., EUR, USD).

        Returns:
            tuple[bool, UUID | None]:
            - On HTTP 200, returns (True, transaction_id) where transaction_id
              is parsed as a UUID if present, otherwise None.
            - On HTTP 402 (payment required/declined), returns (False, None).
            - On HTTP 409 (idempotency conflict), returns (False, None).

        Raises:
            httpx.RequestError: On network or transport errors.
            httpx.HTTPStatusError: For other non-2xx responses after
                ``raise_for_status()``.
        """
        payload = {"amount_cents": amount_cents, "currency": currency}
        headers = {}
        # Propagate Idempotency-Key from request if present (injected by the view)
        if hasattr(self, "_idem_key") and getattr(self, "_idem_key"):
            headers["Idempotency-Key"] = getattr(self, "_idem_key")

        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/charge", json=payload, headers=headers or None)
            if r.status_code == 200:
                data = r.json()
                tx = data.get("transaction_id")
                return True, (uuid.UUID(tx) if tx else None)
            if r.status_code == 402:
                return False, None
            if r.status_code == 409:
                # Idempotency conflict at Payments level: treat as payment failure
                return False, None
            r.raise_for_status()
            return False, None
"""HTTP adapter clients for external services used by the orders domain.

This module provides concrete implementations of the domain ports
(``InventoryPort`` and ``PaymentsPort``) that communicate with external
microservices over HTTP using ``httpx``. The implementations are thin
wrappers that translate domain objects to JSON payloads and interpret
the responses.

It also propagates tracing and safety headers:
- ``X-Request-ID``: correlation id across services (from Django middleware).
- ``Idempotency-Key``: forwarded to Payments when present to ensure E2E idempotency.
"""

import uuid
from typing import List, Optional
import httpx
from django.conf import settings
from django.utils.module_loading import import_string
from .domain import InventoryPort, PaymentsPort, OrderItem

# ContextVar set by RequestIdMiddleware; safe to import via string for tests
REQUEST_ID_CTX = import_string("gateway.middleware.REQUEST_ID_CTX")


def _make_headers(idem_key: Optional[str] = None) -> dict:
    """Build common headers with X-Request-ID and optional Idempotency-Key."""
    headers: dict[str, str] = {}
    try:
        rid = REQUEST_ID_CTX.get()
        if rid and rid != "-":
            headers["X-Request-ID"] = rid
    except Exception:
        pass
    if idem_key:
        headers["Idempotency-Key"] = idem_key
    return headers


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
            reserved; False if reservation failed (e.g. 422 insufficient stock).

        Raises:
            httpx.RequestError: On network or transport errors.
            httpx.HTTPStatusError: On non-2xx responses not explicitly
                handled (after ``raise_for_status()``).
        """
        payload = {"items": [{"sku": i.sku, "quantity": i.quantity} for i in items]}
        headers = _make_headers()
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/reserve", json=payload, headers=headers or None)
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

    Notes:
        If the instance has an ``_idem_key`` attribute (set by the view),
        an ``Idempotency-Key`` header is propagated to enable end-to-end
        idempotency in the payments service.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.PAYMENTS_BASE_URL
        self.timeout = timeout or settings.HTTP_TIMEOUT_SECS
        self._idem_key: Optional[str] = getattr(self, "_idem_key", None)  # optional, set by view

    def charge(self, amount_cents: int, currency: str) -> tuple[bool, Optional[uuid.UUID]]:
        """Attempt to charge a payment via the payments service.

        Args:
            amount_cents: Payment amount in minor currency units (cents).
            currency: Three-letter ISO currency code (e.g., EUR, USD).

        Returns:
            tuple[bool, UUID | None]:
            - On HTTP 200, returns (True, transaction_id) where transaction_id
              is parsed as a UUID if present, otherwise None.
            - On HTTP 402 (payment required/declined), returns (False, None).
            - On HTTP 409 (idempotency conflict), returns (False, None).

        Raises:
            httpx.RequestError: On network or transport errors.
            httpx.HTTPStatusError: For other non-2xx responses after
                ``raise_for_status()``.
        """
        payload = {"amount_cents": amount_cents, "currency": currency}
        headers = _make_headers(self._idem_key)

        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/charge", json=payload, headers=headers or None)

            if r.status_code == 200:
                data = r.json()
                tx = data.get("transaction_id")
                # parse tx as UUID safely
                try:
                    return True, (uuid.UUID(tx) if tx else None)
                except Exception:
                    # unexpected format; treat as missing id
                    return True, None

            if r.status_code == 402:
                return False, None

            if r.status_code == 409:
                # Idempotency conflict at Payments level: treat as payment failure
                return False, None

            r.raise_for_status()
            return False, None
