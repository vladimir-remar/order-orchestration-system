"""Integration tests for the orders create API endpoint.

These tests exercise the HTTP API end-to-end using Django's test client
and the lightweight adapter stubs. Each test documents the expected HTTP
status codes for success and the common failure modes.
"""

import pytest

CREATE_URL = "/api/orders/"


@pytest.mark.django_db
def test_create_order_success(client):
    """POST a valid order and expect 201 with a CONFIRMED status.

    The adapter stubs are configured to accept reasonable quantities and
    positive amounts, so the happy path should return a confirmed order.
    """
    payload = {
        "items": [{"sku": "SKU1", "quantity": 2}],
        "amount_cents": 1500,
        "currency": "EUR",
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 201
    assert r.json()["status"] == "CONFIRMED"


@pytest.mark.django_db
def test_create_order_insufficient_stock(client):
    """If the inventory stub rejects the reservation, return 422."""
    # Stub rejects quantity > 10
    payload = {
        "items": [{"sku": "SKU1", "quantity": 999}],
        "amount_cents": 1500,
        "currency": "EUR",
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 422


@pytest.mark.django_db
def test_create_order_validation_error(client):
    """Invalid payloads should return 400 (Pydantic validation error)."""
    payload = {
        "items": [{"sku": "bad sku!", "quantity": 0}],  # invalid SKU, quantity <=0
        "amount_cents": 0,  # invalid per schema
        "currency": "EU",   # invalid per schema
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_create_order_payment_failed(client, monkeypatch):
    """When the payment adapter declines the charge, return 402 or 400.

    We patch the PaymentsStub to force a decline while keeping the payload
    valid so the request passes validation and inventory reservation.
    """
    # Force payment failure by patching the stub
    from orders import adapters
    monkeypatch.setattr(adapters.PaymentsStub, "charge", lambda _self, a, c: False)

    payload = {
        "items": [{"sku": "SKU1", "quantity": 1}],
        "amount_cents": 1200,
        "currency": "EUR",
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code in (400, 402)  # 402 if payment failed explicitly
