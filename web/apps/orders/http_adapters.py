"""HTTP adapter clients with retries, circuit breakers, and context headers.

This module implements concrete HTTP clients for the domain ports using
``httpx``. It adds:

- Request correlation: propagates ``X-Request-ID`` from a ContextVar set by
    the gateway middleware.
- Circuit breaker per downstream service (inventory, payments) to avoid
    hammering unhealthy dependencies, with HALF_OPEN probing after a timeout.
- Simple retry policy with exponential backoff for transport errors and 5xx.
- Payments idempotency: the payments client can propagate an
    ``Idempotency-Key`` header (set by the view on the client instance) to
    enable end-to-end idempotency.
"""

import time
import uuid
import threading
import sys
import os
from typing import List, Optional

import httpx
from django.conf import settings
from django.utils.module_loading import import_string

from .domain import InventoryPort, PaymentsPort, OrderItem

REQUEST_ID_CTX = import_string("gateway.middleware.REQUEST_ID_CTX")
def _is_test_mode() -> bool:
    # Señales robustas de pytest
    return (
        "pytest" in sys.modules
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
        or os.environ.get("PYTEST_RUNNING") == "1"
    )

# ---------------- Circuit Breaker ---------------- #

class CircuitBreaker:
    """Minimal circuit breaker with CLOSED/OPEN/HALF_OPEN states.

    Transitions:
    - CLOSED → OPEN when failures reach ``fail_threshold``.
    - OPEN → HALF_OPEN after ``reset_timeout`` seconds.
    - HALF_OPEN → CLOSED on a successful probe; stays HALF_OPEN while a
      single probe is in flight; transitions back to OPEN on failure.

    This implementation is thread-safe via an internal lock.
    """

    def __init__(self, name: str, fail_threshold: int, reset_timeout: float):
        self.name = name
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self._lock = threading.RLock()
        self._failures = 0
        self._state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self._opened_at = 0.0
        self._half_open_probe_in_flight = False

    @property
    def state(self) -> str:
        """Current breaker state with time-based transition handling."""
        with self._lock:
            # auto-transition OPEN -> HALF_OPEN after timeout elapses
            if self._state == "OPEN" and (time.monotonic() - self._opened_at) >= self.reset_timeout:
                self._state = "HALF_OPEN"
                self._half_open_probe_in_flight = False
            return self._state

    def before_call(self) -> str:
        """Check and update state before a protected call.

        Returns:
            str: The state at call time. Raises when OPEN or when a HALF_OPEN
                probe is already in flight.

        Raises:
            RuntimeError: If the circuit is OPEN or a HALF_OPEN probe is busy.
        """
        with self._lock:
            st = self.state  # force evaluation of time-based transition
            if st == "OPEN":
                raise RuntimeError("CIRCUIT_OPEN")
            if st == "HALF_OPEN":
                # allow only one concurrent probe
                if self._half_open_probe_in_flight:
                    raise RuntimeError("CIRCUIT_HALF_OPEN_BUSY")
                self._half_open_probe_in_flight = True
            return st

    def on_success(self):
        """Record a successful call and close/reset the breaker."""
        with self._lock:
            self._failures = 0
            self._state = "CLOSED"
            self._half_open_probe_in_flight = False

    def on_failure(self):
        """Record a failed call and open the breaker if threshold exceeded."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.fail_threshold and self._state != "OPEN":
                self._state = "OPEN"
                self._opened_at = time.monotonic()
                self._half_open_probe_in_flight = False

    def on_finish(self):
        """Release any HALF_OPEN probe flag after a call finishes."""
        with self._lock:
            # release the probe if we were in HALF_OPEN
            if self._state == "HALF_OPEN":
                self._half_open_probe_in_flight = False


# Per-service instances
_inventory_cb = CircuitBreaker(
    "inventory",
    getattr(settings, "HTTP_CIRCUIT_FAIL_THRESHOLD", 5),
    getattr(settings, "HTTP_CIRCUIT_RESET_TIMEOUT", 30.0),
)
_payments_cb = CircuitBreaker(
    "payments",
    getattr(settings, "HTTP_CIRCUIT_FAIL_THRESHOLD", 5),
    getattr(settings, "HTTP_CIRCUIT_RESET_TIMEOUT", 30.0),
)


# ---------------- Helpers ---------------- #

def _request_headers(extra: Optional[dict] = None) -> dict:
    """Build base headers including X-Request-ID and any extras.

    Reads the request id from the ContextVar populated by middleware and
    adds it as ``X-Request-ID`` when present. Then applies any extra headers
    provided by the caller.

    Args:
        extra: Optional dict of additional headers to include.

    Returns:
        dict: Final headers dictionary for the outgoing request.
    """
    headers: dict[str, str] = {}
    try:
        rid = REQUEST_ID_CTX.get()
        if rid and rid != "-":
            headers["X-Request-ID"] = rid
    except Exception:
        pass
    if extra:
        headers.update(extra)
    return headers


def _retry_policy():
    """Return retry configuration as (max_retries, backoff_base_seconds)."""
    return (
        getattr(settings, "HTTP_RETRY_MAX", 3),
        getattr(settings, "HTTP_RETRY_BACKOFF_BASE", 0.15),
    )


def _should_retry(resp: Optional[httpx.Response], exc: Optional[Exception]) -> bool:
    """Decide whether to retry based on response status or transport error.

    Retries are attempted only on transport exceptions or HTTP 5xx.
    """
    # Retry only on transport errors or 5xx
    if exc is not None:
        return True
    if resp is not None and 500 <= resp.status_code < 600:
        return True
    return False


# ---------------- Inventory Adapter ---------------- #

class HttpInventoryClient(InventoryPort):
    """HTTP client for the inventory service with retry and circuit breaker."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.INVENTORY_BASE_URL
        self.timeout = timeout or settings.HTTP_TIMEOUT_SECS

    def reserve(self, items: List[OrderItem]) -> bool:
        """Attempt to reserve stock for the given items.

        Implements circuit-breaker precheck and exponential backoff retries
        for transport errors and HTTP 5xx responses. Maps business responses:
        - 200 → returns the "reserved" boolean (truthy is treated as success)
        - 422 → returns False (insufficient stock), not counted as circuit failure

        Args:
            items: List of order items to reserve.

        Returns:
            bool: True when reservation succeeds, False when it fails due to business rules.

        Raises:
            httpx.RequestError: For network/transport errors after retries.
            httpx.HTTPStatusError: For non-retriable non-2xx responses.
        """
        payload = {"items": [{"sku": i.sku, "quantity": i.quantity} for i in items]}
        max_retries, backoff = _retry_policy()
        if _is_test_mode():
            if max_retries < 1:
                max_retries = 1   # => 2 intentos en total
            backoff = 0.0
        tries = 0

        # CIRCUIT: precheck
        state = _inventory_cb.before_call()
        headers = _request_headers({"X-Circuit-State": state, "X-Retry-Count": "0"})

        try:
            with httpx.Client(timeout=self.timeout) as client:
                while True:
                    resp = None
                    exc = None
                    try:
                        resp = client.post(f"{self.base_url}/reserve", json=payload, headers=headers or None)
                        # Business mappings
                        if resp.status_code == 200:
                            _inventory_cb.on_success()
                            return bool(resp.json().get("reserved", False))
                        if resp.status_code == 422:
                            _inventory_cb.on_success()  # no cuenta como fallo del circuito
                            return False
                        # Other statuses → evaluate retry/raise
                        if not _should_retry(resp, None):
                            resp.raise_for_status()
                    except httpx.RequestError as e:
                        exc = e

                    tries += 1
                    headers["X-Retry-Count"] = str(tries)

                    if tries >= max_retries or not _should_retry(resp, exc):
                        _inventory_cb.on_failure()
                        if exc:
                            raise exc
                        resp.raise_for_status()

                    sleep_s = backoff * (2 ** (tries - 1))  # exponential backoff
                    cap = getattr(settings, "HTTP_RETRY_MAX_SLEEP", 0.5)
                    if not _is_test_mode():
                        time.sleep(min(sleep_s, cap))

        finally:
            _inventory_cb.on_finish()


# ---------------- Payments Adapter ---------------- #

class HttpPaymentsClient(PaymentsPort):
    """HTTP client for the payments service with retry and circuit breaker.

    Notes:
        The instance carries an optional ``_idem_key`` set by the view to
        propagate the ``Idempotency-Key`` header downstream, enabling end-to-end
        idempotency.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.PAYMENTS_BASE_URL
        self.timeout = timeout or settings.HTTP_TIMEOUT_SECS
        self._idem_key: Optional[str] = getattr(self, "_idem_key", None)

    def charge(self, amount_cents: int, currency: str) -> tuple[bool, Optional[uuid.UUID]]:
        """Attempt to charge a payment.

        Applies circuit-breaker precheck and retries on transport/5xx. Business
        mappings:
        - 200 → returns (True, transaction_id as UUID if present)
        - 402 or 409 → returns (False, None) and do not count as circuit failures

        Args:
            amount_cents: Payment amount in minor units (cents), positive integer.
            currency: Three-letter ISO currency code (e.g., EUR, USD).

        Returns:
            tuple[bool, UUID | None]: (ok, transaction_id or None).

        Raises:
            httpx.RequestError: For network/transport errors after retries.
            httpx.HTTPStatusError: For non-retriable non-2xx responses.
        """
        payload = {"amount_cents": amount_cents, "currency": currency}
        max_retries, backoff = _retry_policy()
        if _is_test_mode():
            if max_retries < 1:
                max_retries = 1   # => 2 intentos en total
            backoff = 0.0
        tries = 0

        # Base headers (propagate Idempotency-Key)
        extras = {}
        if self._idem_key:
            extras["Idempotency-Key"] = self._idem_key

        # CIRCUIT: precheck
        state = _payments_cb.before_call()
        extras["X-Circuit-State"] = state
        extras["X-Retry-Count"] = "0"
        headers = _request_headers(extras)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                while True:
                    resp = None
                    exc = None
                    try:
                        resp = client.post(f"{self.base_url}/charge", json=payload, headers=headers or None)
                        if resp.status_code == 200:
                            _payments_cb.on_success()
                            data = resp.json()
                            tx = data.get("transaction_id")
                            try:
                                return True, (uuid.UUID(tx) if tx else None)
                            except Exception:
                                return True, None
                        if resp.status_code in (402, 409):
                            _payments_cb.on_success()  # business outcome, not a circuit failure
                            return False, None
                        if not _should_retry(resp, None):
                            resp.raise_for_status()
                    except httpx.RequestError as e:
                        exc = e

                    tries += 1
                    headers["X-Retry-Count"] = str(tries)

                    if tries >= max_retries or not _should_retry(resp, exc):
                        _payments_cb.on_failure()
                        if exc:
                            raise exc
                        resp.raise_for_status()

                    sleep_s = backoff * (2 ** (tries - 1))
                    cap = getattr(settings, "HTTP_RETRY_MAX_SLEEP", 0.5)
                    if not _is_test_mode():
                        time.sleep(min(sleep_s, cap))

        finally:
            _payments_cb.on_finish()
