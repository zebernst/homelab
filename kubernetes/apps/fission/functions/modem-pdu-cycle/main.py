"""Alertmanager webhook target: power-cycle the modem/ONT UniFi PDU outlet.

Policy (dual-signal, gap, circuit breaker) lives in Alertmanager / VMRules.
This function only authenticates and executes the outlet cycle.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response

from unifi_pdu import UniFiPDUClient, UniFiPDUError

logger = logging.getLogger("modem-pdu-cycle")


def _secret_dir() -> Path:
    root = Path("/secrets/fission")
    if not root.exists():
        raise FileNotFoundError("missing /secrets/fission")
    return next(root.iterdir())


def _read_secret(name: str, default: str | None = None) -> str:
    path = _secret_dir() / name
    if path.exists():
        return path.read_text().strip()
    if default is not None:
        return default
    env = os.environ.get(name.upper().replace(".", "_").replace("-", "_"))
    if env:
        return env.strip()
    raise KeyError(f"secret {name} not found")


def _authorized(request: Request, expected: str) -> bool:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() == expected
    return False


async def main(request: Request) -> Response:
    if request.method != "POST":
        return Response(content="Method Not Allowed", status_code=405)

    try:
        expected = _read_secret("webhook.token")
    except (FileNotFoundError, KeyError, StopIteration) as exc:
        logger.error("secret load failed: %s", exc)
        return Response(content="misconfigured", status_code=500)

    if not _authorized(request, expected):
        logger.warning("unauthorized webhook")
        return Response(content="Unauthorized", status_code=401)

    try:
        base_url = _read_secret("unifi.url", "https://unifi")
        username = _read_secret("unifi.username")
        password = _read_secret("unifi.password")
        site = _read_secret("unifi.site", "default")
        mac = _read_secret("pdu.mac")
        outlet_index = int(_read_secret("pdu.outlet_index"))
        off_seconds = float(_read_secret("pdu.off_seconds", "5"))
    except (FileNotFoundError, KeyError, StopIteration, ValueError) as exc:
        logger.error("config load failed: %s", exc)
        return Response(content="misconfigured", status_code=500)

    try:
        with UniFiPDUClient(
            base_url=base_url,
            username=username,
            password=password,
            site=site,
            verify=False,
        ) as client:
            client.power_cycle_outlet(mac, outlet_index, off_seconds=off_seconds)
    except UniFiPDUError as exc:
        logger.exception("unifi pdu cycle failed: %s", exc)
        return Response(content=str(exc), status_code=502)

    return Response(content="ok", status_code=200)
