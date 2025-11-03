"""Unit tests for HTTP adapters to inventory and payments services.

These tests verify that the HTTP clients handle success, failure, and
network error conditions correctly by monkeypatching ``httpx.Client.post``
and asserting the adapter behavior.
"""
import httpx, pytest, uuid
from apps.orders.http_adapters import HttpInventoryClient, HttpPaymentsClient
from apps.orders.domain import OrderItem

class DummyResp:
    """Minimal httpx-like response stub for adapter tests.

    Args:
        status_code (int): HTTP status code to simulate.
        json_data (dict | None): JSON body to return from ``json()``.
    """
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)
    def json(self): return self._json

def test_inventory_reserve_ok(monkeypatch):
    """Inventory adapter returns True on 200 with reserved=True."""
    def fake_post(self, url, json=None, headers=None, **kw):
        return DummyResp(200, {"reserved": True})
    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpInventoryClient(base_url="http://inventory:9001")
    assert client.reserve([OrderItem("SKU1", 2)]) is True

def test_inventory_reserve_fail(monkeypatch):
    """Inventory adapter returns False on 422 reserved failure."""
    def fake_post(self, url, json=None, headers=None, **kw):
        return DummyResp(422, {"reserved": False})
    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpInventoryClient()
    assert client.reserve([OrderItem("SKU1", 99)]) is False

def test_payments_charge_ok(monkeypatch):
    """Payments adapter returns (True, UUID) on 200 with paid and id."""
    def fake_post(self, url, json=None, headers=None, **kw):
        return DummyResp(200, {"paid": True, "transaction_id": str(uuid.uuid4())})
    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpPaymentsClient()
    ok, tx = client.charge(1000, "EUR")
    assert ok is True and isinstance(tx, uuid.UUID)

def test_payments_charge_network_error(monkeypatch):
    """Payments adapter propagates network errors from httpx."""
    def fake_post(self, url, json=None, headers=None, **kw):
        raise httpx.ConnectError("boom")
    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpPaymentsClient()
    with pytest.raises(httpx.ConnectError):
        client.charge(1000, "EUR")
