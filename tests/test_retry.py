import asyncio

import pytest

from app.worker import call_with_retries


class DummyResp:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_retries_on_429(monkeypatch):
    calls = {"count": 0}

    async def fake_call():
        calls["count"] += 1
        # first two calls: 429, then success
        if calls["count"] <= 2:
            return DummyResp(429)
        return DummyResp(200, {"ok": True})

    # speed up sleeps
    async def fake_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    resp = await call_with_retries(fake_call, max_retries=5, base_backoff=0.0)
    assert getattr(resp, "status_code", None) == 200
    assert calls["count"] == 3
