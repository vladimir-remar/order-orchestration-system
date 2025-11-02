"""Integration tests that assert created orders are persisted.

These tests use Django's test client and direct DB assertions to
validate that the HTTP API creates a persisted order row with the
expected values. The tests intentionally use low-level DB access to
avoid coupling to the ORM behavior.
"""

import pytest
from uuid import UUID
from django.db import connection

CREATE_URL = "/api/orders/"


@pytest.mark.django_db
def test_create_persists_order_row_with_uuid_pk(client):
    """POST a valid order and assert a row is created in the DB.

    The test verifies the response contains an `id` string that parses
    as a UUID, and then queries the `orders` table to assert stored
    values (status, total_cents, currency) match expectations.
    """
    payload = {
        "items": [{"sku": "SKU1", "quantity": 2}],
        "amount_cents": 1500,
        "currency": "EUR",
    }
    r = client.post(CREATE_URL, data=payload, content_type="application/json")
    assert r.status_code == 201
    body = r.json()
    oid = body.get("id")
    assert isinstance(oid, str)
    # Validate the id is a proper UUID
    UUID(oid)

    # Check row in DB
    with connection.cursor() as cur:
        cur.execute("select status, total_cents, currency from orders where id = %s", [oid])
        row = cur.fetchone()
    assert row is not None
    status, total_cents, currency = row
    assert status == "CONFIRMED"
    assert total_cents == 1500
    assert currency == "EUR"
