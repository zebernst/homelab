import logging
from pathlib import Path

import calendars
from flask import request

log = logging.getLogger("ics-proxy")


def main() -> tuple[str, int, dict[str, str]]:
    calendar = request.args.get("calendar")
    if not calendar:
        return "Missing ?calendar= query parameter", 400, {}

    log.info("processing calendar=%s", calendar)

    secret_dir = next(Path("/secrets/fission").iterdir())

    match calendar:
        case "on-call":
            url = (secret_dir / "on-call.url").read_text().strip()
            result = calendars.jsm_on_call(url)
        case _:
            return f"Unknown calendar: {calendar}", 404, {}

    log.info("done calendar=%s bytes=%d", calendar, len(result))
    return result, 200, {"Content-Type": "text/calendar; charset=utf-8"}
