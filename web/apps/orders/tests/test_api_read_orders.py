import pytest
from django.urls import reverse
from orders.models import OrderModel
from uuid import uuid4

DETAIL_URL = "/api/orders/{oid}/"
LIST_URL = "/api/orders/"

@pytest.mark.django_db
def test_get_order_by_id_returns_200_and_payload(client):
    # seed
    o = OrderModel.objects.create(
        id=uuid4(),
        status="CONFIRMED",
        total_cents=1500,
        currency="EUR",
        transaction_id=uuid4(),
    )
    r = client.get(DETAIL_URL.format(oid=str(o.id)))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(o.id)
    assert body["status"] == "CONFIRMED"
    assert body["amount_cents"] == 1500
    assert body["currency"] == "EUR"
    assert body["transaction_id"] == str(o.transaction_id)

@pytest.mark.django_db
def test_get_order_not_found_returns_404(client):
    r = client.get(DETAIL_URL.format(oid=str(uuid4())))
    assert r.status_code == 404
    assert r.json()["detail"] == "NOT_FOUND"

@pytest.mark.django_db
def test_list_orders_returns_paginated_array(client):
    # seed 2
    OrderModel.objects.create(id=uuid4(), status="CONFIRMED", total_cents=1500, currency="EUR")
    OrderModel.objects.create(id=uuid4(), status="PENDING", total_cents=9900, currency="EUR")
    r = client.get(LIST_URL)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict) and "results" in body
    assert isinstance(body["results"], list) and len(body["results"]) >= 2
    assert all({"id","status","amount_cents","currency"} <= set(x.keys()) for x in body["results"])
