"""Alertmanager webhook target: power-cycle the modem/ONT UniFi PDU outlet.

Policy (dual-signal, gap, circuit breaker) lives in Alertmanager / VMRules.
This function only authenticates and executes the outlet cycle.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import Response
from pydantic import ValidationError
from pydantic_settings import SettingsError

from settings import Settings
from unifi_pdu import UniFiPDUClient, UniFiPDUError

logger = logging.getLogger("modem-pdu-cycle")


def _authorized(request: Request, expected: str) -> bool:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() == expected
    return False


async def main(request: Request) -> Response:
    if request.method != "POST":
        return Response(content="Method Not Allowed", status_code=405)

    try:
        cfg = Settings.from_fission_secrets()
    except (FileNotFoundError, ValidationError, SettingsError, OSError) as exc:
        logger.error("secret load failed: %s", exc)
        return Response(content="misconfigured", status_code=500)

    if not _authorized(request, cfg.webhook.token.get_secret_value()):
        logger.warning("unauthorized webhook")
        return Response(content="Unauthorized", status_code=401)

    try:
        with UniFiPDUClient(
            base_url=cfg.unifi.url,
            username=cfg.unifi.username,
            password=cfg.unifi.password.get_secret_value(),
            site=cfg.unifi.site,
            verify=False,
        ) as client:
            client.power_cycle_outlet(
                cfg.pdu.mac,
                cfg.pdu.outlet_index,
                off_seconds=cfg.pdu.off_seconds,
            )
    except UniFiPDUError as exc:
        logger.exception("unifi pdu cycle failed: %s", exc)
        return Response(content=str(exc), status_code=502)

    return Response(content="ok", status_code=200)
