"""Lightweight adapter stubs for inventory and payments used in tests
and local development.

These implementations are intentionally simple and deterministic so they
can be used by unit tests and examples without requiring external
services.
"""

from typing import List
from .domain import InventoryPort, PaymentsPort, OrderItem


class InventoryStub(InventoryPort):
    """Simple inventory adapter that simulates reservation behavior.

    The stub accepts quantities in a reasonable range (1..10) and fails
    otherwise. This deterministic behavior makes it suitable for tests.
    """

    def reserve(self, items: List[OrderItem]) -> bool:
        """Attempt to reserve a list of order items.

        Args:
            items: List of OrderItem to reserve.

        Returns:
            True when every item's quantity is between 1 and 10 (inclusive).
            False otherwise.
        """
        # Allow reasonable quantities (<=10) to simulate success
        return all(1 <= it.quantity <= 10 for it in items)


class PaymentsStub(PaymentsPort):
    """Simple payments adapter that simulates charging behavior.

    The stub treats any positive amount as a successful charge. The DTOs
    should ensure amount > 0 in normal flows.
    """

    def charge(self, amount_cents: int, currency: str) -> bool:
        """Charge the given amount in cents for the provided currency.

        Args:
            amount_cents: Amount to charge expressed in integer cents.
            currency: ISO currency code (e.g. 'EUR').

        Returns:
            True if the amount is positive, False otherwise.
        """
        # Success if amount is positive (guaranteed by DTOs)
        return amount_cents > 0
