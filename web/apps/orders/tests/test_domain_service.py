"""Tests for the OrderService domain logic.

These tests exercise the main paths of OrderService using simple stub
implementations for the Inventory and Payments ports. The tests assert
both returned/raised values and that order status transitions are set
appropriately on success and failure.
"""

import pytest
from orders.domain import (
    OrderService,
    Order,
    OrderItem,
    OrderStatus,
)


class StubInventoryOK:
    """Inventory stub that always succeeds on reserve.

    This is used to simulate a healthy inventory service for happy-path
    tests.
    """

    def reserve(self, items):
        return True


class StubInventoryFail:
    """Inventory stub that always fails reserving stock.

    Used to simulate out-of-stock conditions.
    """

    def reserve(self, items):
        return False


class StubPaymentsOK:
    """Payments stub that always succeeds charging."""

    def charge(self, amount_cents, currency):
        return True


class StubPaymentsFail:
    """Payments stub that always fails charging (decline)."""

    def charge(self, amount_cents, currency):
        return False


def test_place_order_ok():
    """Happy path: reserve succeeds and payment succeeds.

    The order should finish in the CONFIRMED state.
    """
    service = OrderService(StubInventoryOK(), StubPaymentsOK())
    order = Order(id=None, items=[OrderItem("SKU1", 2)], total_cents=1000, currency="EUR")
    out = service.place_order(order)
    assert out.status == OrderStatus.CONFIRMED


def test_place_order_empty():
    """Placing an order with no items should raise EMPTY_ORDER."""
    service = OrderService(StubInventoryOK(), StubPaymentsOK())
    with pytest.raises(ValueError) as e:
        service.place_order(Order(id=None, items=[], total_cents=1000, currency="EUR"))
    assert str(e.value) == "EMPTY_ORDER"


def test_place_order_insufficient_stock_sets_state_and_raises():
    """If inventory reservation fails, the order status should be
    STOCK_FAILED and a ValueError('INSUFFICIENT_STOCK') is raised."""
    service = OrderService(StubInventoryFail(), StubPaymentsOK())
    order = Order(id=None, items=[OrderItem("SKU1", 99)], total_cents=1000, currency="EUR")
    with pytest.raises(ValueError) as e:
        service.place_order(order)
    assert str(e.value) == "INSUFFICIENT_STOCK"
    assert order.status == OrderStatus.STOCK_FAILED


def test_place_order_payment_failed_sets_state_and_raises():
    """If charging the payment fails, the order status should be
    PAYMENT_FAILED and a ValueError('PAYMENT_FAILED') is raised."""
    service = OrderService(StubInventoryOK(), StubPaymentsFail())
    order = Order(id=None, items=[OrderItem("SKU1", 1)], total_cents=1000, currency="EUR")
    with pytest.raises(ValueError) as e:
        service.place_order(order)
    assert str(e.value) == "PAYMENT_FAILED"
    assert order.status == OrderStatus.PAYMENT_FAILED
