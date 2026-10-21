"""Alertmanager webhook target: power-cycle the modem/ONT UniFi PDU outlet.

Policy (dual-signal, gap, circuit breaker) lives in Alertmanager / VMRules.
This function only authenticates and executes the outlet cycle.

Note: Fission's python-fastapi runtime invokes ``main(request)`` directly, so
FastAPI ``Depends`` / ``Security`` on this signature are not applied. We still
use FastAPI's ``HTTPBearer`` + ``HTTPException`` for auth parsing and errors.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.responses import Response
from fastapi.security import HTTPBearer
from pydantic import ValidationError
from pydantic_settings import SettingsError

from settings import Settings
from unifi_pdu import UniFiPDUClient, UniFiPDUError

logger = logging.getLogger("modem-pdu-cycle")

_bearer = HTTPBearer()


def _load_settings() -> Settings:
    try:
        return Settings.from_fission_secrets()
    except (FileNotFoundError, ValidationError, SettingsError, OSError) as exc:
        logger.error("secret load failed: %s", exc)
        raise HTTPException(status_code=500, detail="misconfigured") from exc


async def _require_bearer(request: Request, expected: str) -> None:
    credentials = await _bearer(request)
    if credentials.credentials != expected:
        logger.warning("unauthorized webhook")
        raise HTTPException(status_code=403, detail="Not authenticated")


async def main(request: Request) -> Response:
    if request.method != "POST":
        raise HTTPException(status_code=405, detail="Method Not Allowed")

    cfg = _load_settings()
    await _require_bearer(request, cfg.webhook.token.get_secret_value())

    try:
        with UniFiPDUClient(cfg.unifi) as client:
            client.power_cycle_outlet(cfg.pdu, cfg.pdu.modem_outlet_index)
    except UniFiPDUError as exc:
        logger.exception("unifi pdu cycle failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(content="ok", status_code=200)
