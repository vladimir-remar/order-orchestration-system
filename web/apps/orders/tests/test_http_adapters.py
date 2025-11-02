"""Unit tests for the HTTP adapter clients.

These tests patch `httpx.Client.post` to simulate upstream service
responses and network errors. They validate that the adapter clients
correctly interpret success/failure responses and propagate transport
exceptions when appropriate.
"""

import types
import httpx
import pytest
from apps.orders.http_adapters import HttpInventoryClient, HttpPaymentsClient
from apps.orders.domain import OrderItem


class DummyResp:
    """Minimal fake response object used to simulate httpx responses."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._json


def test_inventory_reserve_ok(monkeypatch):
    """Inventory reserve returns True when upstream reports reserved."""

    def fake_post(self, url, json):
        return DummyResp(200, {"reserved": True})

    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)

    client = HttpInventoryClient(base_url="http://inventory:9001")
    ok = client.reserve([OrderItem("SKU1", 2)])
    assert ok is True


def test_inventory_reserve_fail(monkeypatch):
    """Inventory reserve returns False when upstream reports not reserved."""

    def fake_post(self, url, json):
        return DummyResp(200, {"reserved": False})

    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpInventoryClient()
    assert client.reserve([OrderItem("SKU1", 99)]) is False


def test_payments_charge_ok(monkeypatch):
    """Payments charge returns True when upstream reports paid."""

    def fake_post(self, url, json):
        return DummyResp(200, {"paid": True, "transaction_id": 1})

    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpPaymentsClient()
    assert client.charge(1000, "EUR") is True


def test_payments_charge_network_error(monkeypatch):
    """Network/connect errors from httpx are propagated by the client."""

    def fake_post(self, url, json):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    client = HttpPaymentsClient()
    with pytest.raises(httpx.ConnectError):
        client.charge(1000, "EUR")
