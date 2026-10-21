# modem-pdu-cycle

Fission function invoked by Alertmanager when `WanModemRemediate` fires. Power-cycles the ISP modem/ONT outlet on the UniFi USP PDU Pro.

**Policy stays in the alert stack** (dual-signal, 10m gap, 3-strike inhibit). This function only authenticates and cycles the outlet.

Config is loaded via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) from Fission secret **file mounts** (ExternalSecret keys → `/secrets/fission/<mount>/<key>`), not env vars or a single config file.

Webhook auth uses FastAPI’s `HTTPBearer` + `HTTPException`. Fission calls `main(request)` directly (no `Depends`/`Security` injection), so the scheme is invoked explicitly.

## Endpoint

| | |
|---|---|
| **URL** | `http://router.fission.svc.cluster.local/modem-pdu-cycle` |
| **Method** | `POST` |
| **Auth** | `Authorization: Bearer <MODEM_PDU_CYCLE_WEBHOOK_TOKEN>` |

Cluster-only (no Gateway HTTPRoute).

## Secrets

Create a 1Password item named **`modem-pdu-cycle`** with:

| Field | Description |
|---|---|
| `MODEM_PDU_CYCLE_WEBHOOK_TOKEN` | Shared bearer token (also referenced by Alertmanager ExternalSecret) |
| `UNIFI_URL` | e.g. `https://unifi` |
| `UNIFI_USERNAME` | Local UniFi OS user |
| `UNIFI_PASSWORD` | Password |
| `UNIFI_SITE` | Site name (usually `default`) |
| `PDU_MAC` | USP PDU Pro MAC (`AA:BB:CC:DD:EE:FF`) |
| `PDU_OUTLET_INDEX` | 1-based outlet index for the modem/ONT |
| `PDU_OFF_SECONDS` | Seconds off before power-on (e.g. `5`) |

Also ensure the Alertmanager 1Password extract can read `MODEM_PDU_CYCLE_WEBHOOK_TOKEN` from this item (wired in `victoria-metrics` ExternalSecret `dataFrom`).

## Development

```bash
task fission:_update-literal NAME=modem-pdu-cycle
# or
task fission:check NAME=modem-pdu-cycle
```

```bash
cd kubernetes/apps/fission/functions/modem-pdu-cycle
uv run pytest
```
