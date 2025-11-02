"""API tests for transaction_id behavior on order creation.

This module verifies that the create-order endpoint returns a
non-empty transaction identifier in UUID format when an order is
successfully created.
"""
import pytest
from uuid import UUID

CREATE_URL = "/api/orders/"

@pytest.mark.django_db
def test_create_order_returns_transaction_id(client, settings):
    """Create order returns a valid transaction_id (UUID).

    The test posts a minimal, valid payload and asserts that:
    - The endpoint responds with HTTP 201.
    - The JSON body contains a non-empty ``transaction_id`` field.
    - The value is a valid UUID string.

    Notes:
        The settings are adjusted to disable HTTP adapters so the
        in-process stubs are used for deterministic behavior.
    """

    settings.USE_HTTP_ADAPTERS = False  # use deterministic stubs
    payload = {
        "items": [{"sku": "SKU1", "quantity": 2}],
        "amount_cents": 1500,
        "currency": "EUR",
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 201
    body = r.json()
    assert "transaction_id" in body and body["transaction_id"]
    UUID(body["transaction_id"])  # validate format
