"""API idempotency tests for the orders service.

These tests verify the Create Order endpoint behaves idempotently when an
``Idempotency-Key`` header is provided:

- Replaying the same payload with the same key returns HTTP 200 and the
    same order id.
- Using the same key with a different payload returns HTTP 409 conflict.
"""

import pytest
from uuid import UUID

CREATE_URL = "/api/orders/"

@pytest.mark.django_db
def test_idempotent_same_payload_returns_same_order_and_200_on_retry(client, settings):
    """Retrying with same key and payload returns 200 and same order id.

    The first request creates an order (201). The second request with the
    same idempotency key and identical payload returns 200 and the same id.
    """
    settings.USE_HTTP_ADAPTERS = False  # use stubs in tests
    key = "idem-123"
    payload = {"items":[{"sku":"SKU1","quantity":2}],"amount_cents":1500,"currency":"EUR"}

    r1 = client.post(CREATE_URL, data=payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
    assert r1.status_code == 201
    oid1 = r1.json()["id"]; UUID(oid1)

    r2 = client.post(CREATE_URL, data=payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
    assert r2.status_code == 200
    assert r2.json()["id"] == oid1

@pytest.mark.django_db
def test_idempotent_conflict_on_different_payload_with_same_key(client):
    """Different payload with same key returns 409 idempotency conflict.

    First request may return 201 (created) or 200 (replayed). A subsequent
    request using the same key but a different payload must return 409.
    """
    key = "idem-456"
    p1 = {"items":[{"sku":"SKU1","quantity":1}],"amount_cents":100,"currency":"EUR"}
    p2 = {"items":[{"sku":"SKU1","quantity":2}],"amount_cents":200,"currency":"EUR"}

    r1 = client.post(CREATE_URL, data=p1, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
    assert r1.status_code in (201, 200)

    r2 = client.post(CREATE_URL, data=p2, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
    assert r2.status_code == 409
    assert r2.json()["detail"] == "IDEMPOTENCY_CONFLICT"
