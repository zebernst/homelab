"""UniFi USP PDU outlet power-cycle via classic Network API outlet_overrides."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("modem-pdu-cycle")


class UniFiPDUError(Exception):
    """Raised when UniFi API login or outlet control fails."""


def merge_outlet_overrides(
    existing: list[dict[str, Any]],
    outlet_index: int,
    relay_state: bool,
) -> list[dict[str, Any]]:
    """Return a full outlet_overrides list with one index updated.

    Preserves sibling overrides verbatim. Creates an entry when missing.
    """
    overrides = [dict(o) for o in existing]
    for entry in overrides:
        if entry.get("index") == outlet_index:
            entry["relay_state"] = relay_state
            return overrides
    overrides.append({"index": outlet_index, "relay_state": relay_state})
    return overrides


class UniFiPDUClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        site: str = "default",
        verify: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.site = site
        self.client = httpx.Client(
            base_url=self.base_url,
            verify=verify,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> UniFiPDUClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def login(self) -> None:
        # UniFi OS local login
        resp = self.client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if resp.status_code >= 400:
            raise UniFiPDUError(f"login failed: HTTP {resp.status_code}")
        # CSRF for subsequent mutating calls
        csrf = resp.headers.get("x-csrf-token")
        if csrf:
            self.client.headers["X-CSRF-Token"] = csrf

    def _api(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"/proxy/network/api/s/{self.site}{path}"
        resp = self.client.request(method, url, **kwargs)
        if resp.status_code >= 400:
            raise UniFiPDUError(f"{method} {path} failed: HTTP {resp.status_code}: {resp.text[:200]}")
        return resp

    def get_device_by_mac(self, mac: str) -> dict[str, Any]:
        mac_norm = mac.lower()
        resp = self._api("GET", "/stat/device")
        data = resp.json().get("data") or []
        for device in data:
            if str(device.get("mac", "")).lower() == mac_norm:
                return device
        raise UniFiPDUError(f"device not found for mac={mac}")

    def set_outlet_relay(self, device: dict[str, Any], outlet_index: int, relay_state: bool) -> None:
        device_id = device.get("_id")
        if not device_id:
            raise UniFiPDUError("device missing _id")
        existing = list(device.get("outlet_overrides") or [])
        overrides = merge_outlet_overrides(existing, outlet_index, relay_state)
        self._api(
            "PUT",
            f"/rest/device/{device_id}",
            json={"outlet_overrides": overrides},
        )
        # Keep local copy in sync for a subsequent call in the same cycle
        device["outlet_overrides"] = overrides

    def power_cycle_outlet(
        self,
        mac: str,
        outlet_index: int,
        *,
        off_seconds: float = 5.0,
    ) -> None:
        self.login()
        device = self.get_device_by_mac(mac)
        logger.info("power-cycle start mac=%s outlet=%s", mac, outlet_index)
        self.set_outlet_relay(device, outlet_index, False)
        try:
            time.sleep(off_seconds)
        finally:
            # Best-effort restore on even if sleep/re-fetch fails mid-cycle
            device = self.get_device_by_mac(mac)
            self.set_outlet_relay(device, outlet_index, True)
        logger.info("power-cycle complete mac=%s outlet=%s", mac, outlet_index)
