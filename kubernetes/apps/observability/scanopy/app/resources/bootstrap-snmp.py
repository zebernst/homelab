#!/usr/bin/env python3
"""Ensure the UniFi SNMP credential exists and is assigned to the Scanopy network."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import UUID

API_URL = os.environ.get("SCANOPY_API_URL", "http://scanopy.observability.svc.cluster.local:60072")
API_KEY = os.environ.get("SCANOPY_USER_API_KEY", "")
NETWORK_ID = os.environ.get("SCANOPY_NETWORK_ID", "")
COMMUNITY_FILE = "/run/secrets/unifi-snmp-community"
CREDENTIAL_NAME = "UniFi SNMP"


def log(message: str) -> None:
    print(message, flush=True)


def missing_config() -> bool:
    return not API_KEY or not NETWORK_ID


def request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API_URL.rstrip('/')}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def wait_for_server() -> None:
    health_url = f"{API_URL.rstrip('/')}/api/health"
    for attempt in range(60):
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)
    raise RuntimeError(f"Scanopy server not ready at {health_url}")


def find_credential_id() -> str | None:
    payload = request("GET", "/api/v1/credentials?type=SnmpV2c&limit=100")
    items = payload.get("data", [])
    for item in items:
        if item.get("base", {}).get("name") == CREDENTIAL_NAME:
            return item["id"]
    return None


def create_credential() -> str:
    payload = request(
        "POST",
        "/api/v1/credentials",
        {
            "base": {
                "name": CREDENTIAL_NAME,
                "credential_type": {
                    "type": "SnmpV2c",
                    "community": {"mode": "FilePath", "path": COMMUNITY_FILE},
                },
                "tags": [],
            }
        },
    )
    return payload["data"]["id"]


def assign_credential(credential_id: str) -> None:
    UUID(NETWORK_ID)
    network_payload = request("GET", f"/api/v1/networks/{NETWORK_ID}")
    network = network_payload["data"]
    credential_ids = network.get("base", {}).get("credential_ids", [])
    if credential_id not in credential_ids:
        credential_ids.append(credential_id)
    network["base"]["credential_ids"] = credential_ids
    request("PUT", f"/api/v1/networks/{NETWORK_ID}", network)


def main() -> int:
    if missing_config():
        log("SNMP bootstrap skipped: SCANOPY_USER_API_KEY or SCANOPY_NETWORK_ID not set")
        return 0

    wait_for_server()

    try:
        credential_id = find_credential_id()
        if credential_id is None:
            log(f"Creating Scanopy SNMP credential '{CREDENTIAL_NAME}'")
            credential_id = create_credential()
        else:
            log(f"Using existing Scanopy SNMP credential '{CREDENTIAL_NAME}' ({credential_id})")

        assign_credential(credential_id)
        log("UniFi SNMP credential assigned to Scanopy network")
        return 0
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        log(f"SNMP bootstrap failed: HTTP {error.code}: {body}")
        return 1
    except Exception as error:  # noqa: BLE001
        log(f"SNMP bootstrap failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
