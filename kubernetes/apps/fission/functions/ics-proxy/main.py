from pathlib import Path

import calendars
from flask import request


def main() -> tuple[str, int, dict[str, str]]:
    calendar = request.args.get("calendar")
    if not calendar:
        return "Missing ?calendar= query parameter", 400, {}

    secret_dir = next(Path("/secrets/fission").iterdir())

    match calendar:
        case "on-call":
            url = (secret_dir / "on-call.url").read_text().strip()
            result = calendars.jsm_on_call(url)
        case _:
            return f"Unknown calendar: {calendar}", 404, {}

    return result, 200, {"Content-Type": "text/calendar; charset=utf-8"}
