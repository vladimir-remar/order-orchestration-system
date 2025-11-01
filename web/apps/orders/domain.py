"""Domain models, ports and service for orders.

This module contains simple dataclasses used as DTOs for orders, protocol
definitions (ports) for external dependencies such as inventory and
payments, and the domain service that orchestrates placing an order.
"""

from dataclasses import dataclass
from typing import Protocol, List
from enum import Enum


# ---- Enums ----
class OrderStatus(str, Enum):
    """Enumeration of the possible order statuses.
    These statuses are used by the domain service to reflect the order
    lifecycle."""

    CREATED = "CREATED"
    STOCK_RESERVED = "STOCK_RESERVED"
    STOCK_FAILED = "STOCK_FAILED"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


# ---- Entities / DTOs ----
@dataclass(frozen=True)
class OrderItem:
    """A single line item in an order.

    Attributes:
        sku: The stock-keeping unit identifier for the product.
        quantity: Number of units requested for this SKU.

    The dataclass is frozen because items are immutable once created in
    the context of an order.
    """

    sku: str
    quantity: int


@dataclass
class Order:
    """Container for order data.

    Attributes:
        id: Persistent identifier for the order, or None if not yet saved.
        items: List of OrderItem objects that make up the order.
        status: Current OrderStatus.
        total_cents: Order total expressed in integer cents to avoid
            floating point rounding issues.
        currency: ISO currency code (e.g. 'EUR').
    """

    id: int | None
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.CREATED
    total_cents: int = 0
    currency: str = "EUR"


# ---- Ports (DIP) ----
class InventoryPort(Protocol):
    """Port describing inventory operations used by the domain.

    Implementers should provide a reservation mechanism for a list of
    OrderItem instances.
    """

    def reserve(self, items: List[OrderItem]) -> bool:
        """Attempt to reserve the provided items.

        Args:
            items: List of OrderItem to reserve.

        Returns:
            True if reservation succeeded, False otherwise.

        Raises:
            NotImplementedError: If the method is not implemented by the
                concrete class.
        """
        raise NotImplementedError()


class PaymentsPort(Protocol):
    """Port describing payment operations used by the domain.

    Implementers should provide charging functionality and return a
    boolean indicating success.
    """

    def charge(self, amount_cents: int, currency: str) -> bool:
        """Charge the given amount in the specified currency.

        Args:
            amount_cents: Amount to charge, in integer cents.
            currency: Currency code (ISO), e.g. 'EUR'.

        Returns:
            True if the charge was successful, False otherwise.

        Raises:
            NotImplementedError: If the method is not implemented by the
                concrete class.
        """
        raise NotImplementedError()


# ---- Domain service ----
class OrderService:
    """Domain service responsible for placing orders.

    This service orchestrates the steps required to place an order using
    the provided ports: reserve inventory and charge payment. It does not
    handle persistence or external I/O.
    """

    def __init__(self, inventory: InventoryPort, payments: PaymentsPort):
        """Initialize the service with required dependencies.

        Args:
            inventory: InventoryPort used to reserve stock.
            payments: PaymentsPort used to charge customers.
        """
        self.inventory = inventory
        self.payments = payments

    def place_order(self, order: Order) -> Order:
        """Place an order: validate, reserve stock, charge payment, confirm.

        The method updates `order.status` at meaningful points in the
        process so callers can observe intermediate states (e.g.
        STOCK_RESERVED, PAID, CONFIRMED). On failures the status is set to
        a failure state (STOCK_FAILED or PAYMENT_FAILED) and a ValueError
        with a short error code is raised.

        Args:
            order: Order instance to process.

        Returns:
            The same Order instance with status updated to
            OrderStatus.CONFIRMED on success.

        Raises:
            ValueError: With one of the following codes:
                'EMPTY_ORDER' if the order has no items.
                'INSUFFICIENT_STOCK' if inventory reservation fails.
                'PAYMENT_FAILED' if charging the payment fails.
        """
        if not order.items:
            raise ValueError("EMPTY_ORDER")

        # 1) Reserve stock
        if not self.inventory.reserve(order.items):
            order.status = OrderStatus.STOCK_FAILED
            raise ValueError("INSUFFICIENT_STOCK")
        order.status = OrderStatus.STOCK_RESERVED

        # 2) Charge payment
        if not self.payments.charge(order.total_cents, order.currency):
            order.status = OrderStatus.PAYMENT_FAILED
            raise ValueError("PAYMENT_FAILED")
        order.status = OrderStatus.PAID

        # 3) Confirm
        order.status = OrderStatus.CONFIRMED
        return order
