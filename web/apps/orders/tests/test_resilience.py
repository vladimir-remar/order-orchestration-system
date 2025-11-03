# web/apps/orders/tests/test_resilience.py
import httpx
import pytest

def test_inventory_retries_on_5xx(monkeypatch, settings):
    # retries rápidos y al menos 1 reintento
    settings.HTTP_RETRY_MAX = 1
    settings.HTTP_RETRY_BACKOFF_BASE = 0.0

    # reset circuit breaker para no arrastrar estado
    from apps.orders.http_adapters import _inventory_cb
    _inventory_cb.on_success()

    calls = {"n": 0}

    def fake_post(self, url, json=None, headers=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            class R:
                status_code = 500
                # importante: no definas raise_for_status que lance aquí,
                # porque el adapter no debería invocarlo en paso intermedio.
                def raise_for_status(self): pass
            return R()
        # segundo intento: 200 OK
        class R2:
            status_code = 200
            def json(self): return {"reserved": True}
        return R2()

    # aplica los patches
    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    monkeypatch.setattr("time.sleep", lambda *a, **k: None, raising=True)

    from apps.orders.http_adapters import HttpInventoryClient
    ok = HttpInventoryClient(base_url="http://x").reserve([])
    assert ok is True
    assert calls["n"] == 2


def test_payments_no_retry_on_402(monkeypatch, settings):
    settings.HTTP_RETRY_MAX = 3
    settings.HTTP_RETRY_BACKOFF_BASE = 0.0

    from apps.orders.http_adapters import _payments_cb
    _payments_cb.on_success()

    def fake_post(self, url, json=None, headers=None, **kwargs):
        class R:
            status_code = 402
        return R()

    monkeypatch.setattr(httpx.Client, "post", fake_post, raising=True)
    monkeypatch.setattr("time.sleep", lambda *a, **k: None, raising=True)

    from apps.orders.http_adapters import HttpPaymentsClient
    ok, tx = HttpPaymentsClient(base_url="http://x").charge(1000, "EUR")
    assert ok is False and tx is None
