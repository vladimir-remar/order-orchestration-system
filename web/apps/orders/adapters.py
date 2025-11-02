"""In-process stub adapters for the orders domain ports.

These stubs implement ``InventoryPort`` and ``PaymentsPort`` without any
network calls. They are intended for unit tests and local development
where deterministic behavior is useful and external services are not
required.
"""

import uuid
from typing import List, Tuple, Optional
from .domain import InventoryPort, PaymentsPort, OrderItem

class InventoryStub(InventoryPort):
    """Stub implementation of ``InventoryPort``.

    Approves reservations when each item's quantity is between 1 and 10
    (inclusive). This is a deterministic rule for testing purposes.
    """

    def reserve(self, items: List[OrderItem]) -> bool:
        """Attempt to reserve the provided items.

        Args:
            items: List of order items to reserve.

        Returns:
            bool: True if every item's quantity is in the inclusive range
            [1, 10]; otherwise False.
        """
        return all(1 <= it.quantity <= 10 for it in items)

class PaymentsStub(PaymentsPort):
    """Stub implementation of ``PaymentsPort``.

    Approves charges with a positive amount and returns a generated UUID
    as the transaction id. Non-positive amounts are rejected.
    """

    def charge(self, amount_cents: int, currency: str) -> tuple[bool, Optional[uuid.UUID]]:
        """Charge a mock payment.

        Args:
            amount_cents: Amount to charge in minor units (cents).
            currency: Three-letter ISO currency code (e.g., EUR, USD).

        Returns:
            tuple[bool, Optional[uuid.UUID]]: A tuple ``(paid, transaction_id)``
            where ``paid`` is True when ``amount_cents`` > 0 and
            ``transaction_id`` is a randomly generated UUID for approved
            payments; otherwise ``(False, None)``.
        """
        if amount_cents <= 0:
            return (False, None)
        return (True, uuid.uuid4())  # Demo: generate a valid UUID
