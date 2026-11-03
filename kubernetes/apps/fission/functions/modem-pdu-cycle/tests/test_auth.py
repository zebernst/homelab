from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import main as modem_main
from settings import Settings


def _request(method: str = "POST", authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/modem-pdu-cycle",
        "raw_path": b"/modem-pdu-cycle",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    return Request(scope)


def _settings(tmp_path: Path) -> Settings:
    mount = tmp_path / "abc"
    mount.mkdir()
    (mount / "webhook.token").write_text("expected")
    (mount / "unifi.username").write_text("admin")
    (mount / "unifi.password").write_text("pw")
    (mount / "pdu.mac").write_text("aa:bb:cc:dd:ee:ff")
    (mount / "pdu.modem_outlet_index").write_text("1")
    return Settings(_secrets_dir=mount)


@pytest.mark.asyncio
async def test_require_bearer_accepts_matching_token():
    await modem_main._require_bearer(
        _request(authorization="Bearer secret"),
        "secret",
    )


@pytest.mark.asyncio
async def test_require_bearer_rejects_missing():
    with pytest.raises(HTTPException) as exc:
        await modem_main._require_bearer(_request(), "secret")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_bearer_rejects_wrong_token():
    with pytest.raises(HTTPException) as exc:
        await modem_main._require_bearer(
            _request(authorization="Bearer nope"),
            "secret",
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_main_method_not_allowed():
    with pytest.raises(HTTPException) as exc:
        await modem_main.main(_request(method="GET"))
    assert exc.value.status_code == 405


@pytest.mark.asyncio
async def test_main_unauthorized(tmp_path: Path):
    cfg = _settings(tmp_path)
    with patch.object(modem_main, "_load_settings", return_value=cfg):
        with pytest.raises(HTTPException) as exc:
            await modem_main.main(_request(authorization="Bearer wrong"))
        assert exc.value.status_code == 403
