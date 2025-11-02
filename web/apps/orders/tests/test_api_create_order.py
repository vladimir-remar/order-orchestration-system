"""API tests for the create-order endpoint.

These tests exercise the orders HTTP API for the main scenarios: successful
creation, insufficient stock, payment failure, and payload validation error.
They rely on in-process stubs from ``apps.orders.adapters`` for deterministic
behavior.
"""
import pytest
from orders import adapters  # stubs live here
from orders.domain import OrderService


CREATE_URL = "/api/orders/"

@pytest.mark.django_db
def test_create_order_payment_failed(client, settings, monkeypatch):
    """Returns 402 when payment fails (PAYMENT_FAILED maps to 402)."""
    settings.USE_HTTP_ADAPTERS = False  # por si acaso

    # Inyectamos un servicio controlado a través del provider de la vista
    class DummyInventory:
        def reserve(self, items): return True

    class DummyPayments:
        # firma nueva: (bool, UUID|None)
        def charge(self, amount_cents, currency): return (False, None)

    # IMPORTANTE: parchear el *símbolo* usado por la vista
    monkeypatch.setattr(
        "apps.orders.providers.get_order_service",
        lambda: OrderService(DummyInventory(), DummyPayments()),
        raising=True,
    )

    payload = {"items":[{"sku":"SKU1","quantity":1}],"amount_cents":1200,"currency":"EUR"}
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 402
    assert r.json()["detail"] == "PAYMENT_FAILED"

@pytest.mark.django_db
def test_create_order_insufficient_stock(client, settings, monkeypatch):
    """Returns 422 when the inventory stub denies the reservation."""
    settings.USE_HTTP_ADAPTERS = False
    monkeypatch.setattr(adapters.InventoryStub, "reserve", lambda self, items: False)
    import uuid
    monkeypatch.setattr(adapters.PaymentsStub, "charge", lambda self, a, c: (True, uuid.uuid4()))
    payload = {"items":[{"sku":"SKU1","quantity":999}],"amount_cents":1500,"currency":"EUR"}
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 422

@pytest.mark.django_db
def test_create_order_payment_failed(client, settings, monkeypatch):
    """Returns 402 when payment fails (PAYMENT_FAILED maps to 402)."""
    settings.USE_HTTP_ADAPTERS = False
    monkeypatch.setattr(adapters.InventoryStub, "reserve", lambda self, items: True)
    monkeypatch.setattr(adapters.PaymentsStub, "charge", lambda self, a, c: (False, None))
    payload = {"items":[{"sku":"SKU1","quantity":1}],"amount_cents":1200,"currency":"EUR"}
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 402  # we now map PAYMENT_FAILED → 402

@pytest.mark.django_db
def test_create_order_validation_error(client):
    """Returns 400 when the payload fails DTO validation."""
    payload = {
        "items": [{"sku": "bad sku!", "quantity": 0}],
        "amount_cents": 0,
        "currency": "EU",
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 400
