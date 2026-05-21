# ics-proxy

Fission function that proxies and transforms remote iCalendar (`.ics`) feeds. It adds token-based access control so calendar apps can subscribe to upstream feeds without exposing their raw URLs, and applies calendar-specific fixes so events display correctly in common clients.

## Endpoint

| | |
|---|---|
| **URL** | `https://fn.zebernst.dev/ics/proxy` |
| **Method** | `GET` |
| **Response** | `text/calendar; charset=utf-8` |

### Query parameters

| Parameter | Required | Description |
|---|---|---|
| `calendar` | yes | Which feed to fetch. See [Supported calendars](#supported-calendars). |
| `token` | yes | Shared secret that must match `FISSION_AUTH_TOKEN` in 1Password. |

### Example

```text
https://fn.zebernst.dev/ics/proxy?calendar=on-call&token=<token>
```

Use this URL as a calendar subscription in Apple Calendar, Google Calendar, or any other iCal client.

### Responses

| Status | Meaning |
|---|---|
| `200` | Transformed `.ics` body |
| `400` | Missing `?calendar=` query parameter |
| `401` | Missing or invalid `?token=` |
| `404` | Unknown `calendar` value |

## Supported calendars

### `on-call`

Proxies the Jira Service Management (JSM) on-call schedule ICS feed.

**Transformations** (see `calendars.py`):

1. **Normalize line folding** — strips RFC 5545 folded whitespace so downstream parsers see clean lines.
2. **Rename events** — replaces every `SUMMARY` with `Platform: On Call`.
3. **All-day events** — converts `DTSTART`/`DTEND` from date-time values to all-day (`VALUE=DATE`) events. `DTEND` is incremented by one day so the end date is inclusive, which many calendar apps expect for all-day spans.

The upstream JSM feed URL is stored in 1Password as `JSM_ICS_URL` and is never exposed to clients.

## Architecture

```
Calendar app
    │
    ▼
HTTPRoute (fn.zebernst.dev/ics/proxy)
    │
    ▼
Fission router ──► HTTPTrigger (/ics/proxy)
                        │
                        ▼
                   ics-proxy function
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    1Password secret            Upstream ICS feed
    (token, on-call.url)        (JSM on-call schedule)
```

| Resource | Purpose |
|---|---|
| `externalsecret.yaml` | Syncs `ics-proxy-secret` from 1Password item `ics-proxy` |
| `package.yaml` | Base64-encoded source archive deployed to Fission |
| `function.yaml` | Fission Function using `python-fastapi` environment |
| `trigger.yaml` | Maps `GET /ics/proxy` to the function |
| `httproute.yaml` | Exposes the trigger via the external Gateway at `fn.zebernst.dev` |

## Secrets

Create a 1Password item named **`ics-proxy`** with these fields:

| Field | Maps to | Description |
|---|---|---|
| `JSM_ICS_URL` | `on-call.url` | Private ICS URL from JSM on-call schedule settings |
| `FISSION_AUTH_TOKEN` | `token` | Random string used as the `?token=` query parameter |

The ExternalSecret refreshes every 5 minutes. Fission mounts the resulting Kubernetes secret at `/secrets/fission/<hash>/`.

## Development

Source lives in this directory. Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml`, `uv.lock`). Runtime dependencies (`httpx`) are bundled into the package; `fastapi` is provided by the Fission `python-fastapi` environment image.

After editing Python source, sync the embedded package literal and rebuild on the cluster:

```bash
# Update package.yaml literal and rebuild on cluster
task fission:sync NAME=ics-proxy

# Verify package.yaml matches source (no cluster changes)
task fission:check NAME=ics-proxy

# Rebuild on cluster without re-syncing source
task fission:rebuild NAME=ics-proxy
```

Pre-commit hooks automatically update `package.yaml` when `.py` files in this directory change.

### Adding a calendar

1. Add a handler branch in `main.py` (`match calendar:`).
2. Implement fetch/transform logic in `calendars.py`.
3. Add any new secret keys to `externalsecret.yaml` and 1Password.
4. Run `task fission:sync NAME=ics-proxy`.

## Files

| File | Description |
|---|---|
| `main.py` | FastAPI entrypoint — auth, routing, response headers |
| `calendars.py` | Per-calendar fetch and ICS transformation logic |
| `pyproject.toml` | Python project metadata and dependency constraints |
| `package.yaml` | Fission Package (generated literal — do not edit by hand) |
| `function.yaml` | Fission Function spec |
| `trigger.yaml` | Fission HTTPTrigger spec |
| `httproute.yaml` | Gateway API route for external ingress |
| `externalsecret.yaml` | ExternalSecret for 1Password-backed credentials |
| `kustomization.yaml` | Kustomize entry point for Flux |
