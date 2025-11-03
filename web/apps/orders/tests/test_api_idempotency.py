import pytest
from uuid import UUID

CREATE_URL = "/api/orders/"

@pytest.mark.django_db
def test_idempotent_same_payload_returns_same_order_and_status_on_retry(client, settings):
    settings.USE_HTTP_ADAPTERS = False  # stubs

    key = "idem-same-1"
    payload = {
        "items": [{"sku": "SKU1", "quantity": 2}],
        "amount_cents": 1500,
        "currency": "EUR",
    }

    # 1º intento
    r1 = client.post(CREATE_URL, data=payload, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": key})
    assert r1.status_code in (201, 422, 402)  # cualquiera válido según negocio
    body1 = r1.json()

    # 2º intento (replay)
    r2 = client.post(CREATE_URL, data=payload, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": key})
    assert r2.status_code == r1.status_code
    assert r2.json() == body1
    assert r2.headers.get("Idempotent-Replay") == "true"

@pytest.mark.django_db
def test_idempotent_conflict_on_different_payload_with_same_key(client, settings):
    settings.USE_HTTP_ADAPTERS = False
    key = "idem-conflict-1"

    p1 = {"items":[{"sku":"SKU1","quantity":2}],"amount_cents":1500,"currency":"EUR"}
    p2 = {"items":[{"sku":"SKU1","quantity":3}],"amount_cents":1500,"currency":"EUR"}

    r1 = client.post(CREATE_URL, data=p1, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": key})
    assert r1.status_code in (201, 422, 402)

    r2 = client.post(CREATE_URL, data=p2, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": key})
    assert r2.status_code == 409
    assert r2.json()["detail"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.django_db
def test_idempotent_replay_preserves_422_status(client, settings, monkeypatch):
    settings.USE_HTTP_ADAPTERS = False
    from apps.orders import adapters
    # fuerza stock insuficiente
    monkeypatch.setattr(adapters.InventoryStub, "reserve", lambda self, items: False)
    import uuid
    monkeypatch.setattr(adapters.PaymentsStub, "charge", lambda self, a, c: (True, uuid.uuid4()))

    key = "idem-422"
    payload = {"items":[{"sku":"SKU1","quantity":999}],"amount_cents":1500,"currency":"EUR"}

    r1 = client.post(CREATE_URL, data=payload, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": key})
    assert r1.status_code == 422

    r2 = client.post(CREATE_URL, data=payload, content_type="application/json", **{"HTTP_IDEMPOTENCY_KEY": key})
    assert r2.status_code == 422
    assert r2.json() == r1.json()
    assert r2.headers.get("Idempotent-Replay") == "true"
