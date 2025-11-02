"""Unit tests for the OrderService domain orchestration.

These tests validate the behavior of placing orders under different
conditions: happy path, empty orders, insufficient stock, and payment
failures. Stubbed ports are used to deterministically drive outcomes.
"""

import pytest
from apps.orders.domain import OrderService, Order, OrderItem, OrderStatus
import uuid

class StubInventoryOK:
    """Inventory stub that always reserves successfully."""
    def reserve(self, items): return True

class StubInventoryFail:
    """Inventory stub that always fails to reserve (insufficient stock)."""
    def reserve(self, items): return False

class StubPaymentsOK:
    # new signature -> (bool, UUID|None)
    """Payments stub that always approves charges and returns a UUID."""
    def charge(self, amount_cents, currency): return (True, uuid.uuid4())

class StubPaymentsFail:
    """Payments stub that always declines charges."""
    def charge(self, amount_cents, currency): return (False, None)

def test_place_order_ok():
    """Happy path: reserve succeeds and payment is approved.

    Asserts the returned order is confirmed and a transaction_id is set.
    """
    service = OrderService(StubInventoryOK(), StubPaymentsOK())
    order = Order(id=None, items=[OrderItem("SKU1", 2)], total_cents=1000, currency="EUR")
    out = service.place_order(order)
    assert out.status == OrderStatus.CONFIRMED
    assert out.transaction_id is not None

def test_place_order_empty():
    """Validation: placing an empty order raises EMPTY_ORDER error."""
    service = OrderService(StubInventoryOK(), StubPaymentsOK())
    with pytest.raises(ValueError) as e:
        service.place_order(Order(id=None, items=[], total_cents=1000, currency="EUR"))
    assert str(e.value) == "EMPTY_ORDER"

def test_place_order_insufficient_stock():
    """Domain error: insufficient stock raises INSUFFICIENT_STOCK."""
    service = OrderService(StubInventoryFail(), StubPaymentsOK())
    with pytest.raises(ValueError) as e:
        service.place_order(Order(id=None, items=[OrderItem("SKU1", 99)], total_cents=1000, currency="EUR"))
    assert str(e.value) == "INSUFFICIENT_STOCK"

def test_place_order_payment_failed_sets_state_and_raises():
    """Payment error: charge fails, order status set and error raised.

    Verifies the service sets the order status to PAYMENT_FAILED and raises
    a ValueError with code "PAYMENT_FAILED".
    """
    service = OrderService(StubInventoryOK(), StubPaymentsFail())
    order = Order(id=None, items=[OrderItem("SKU1", 1)], total_cents=1000, currency="EUR")
    with pytest.raises(ValueError) as e:
        service.place_order(order)
    assert str(e.value) == "PAYMENT_FAILED"
    assert order.status == OrderStatus.PAYMENT_FAILED
