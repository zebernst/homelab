from pathlib import Path
import re

import httpx
from flask import request


def main() -> tuple[str, int, dict[str, str]]:
    calendar = request.args.get("calendar")
    if not calendar:
        return "Missing ?calendar= query parameter", 400, {}

    secret_dir = next(Path("/secrets/fission").iterdir())
    config_dir = next(Path("/configs/fission").iterdir())

    url_file = secret_dir / f"{calendar}.url"
    if not url_file.exists():
        return f"Unknown calendar: {calendar}", 404, {}

    url = url_file.read_text().strip()
    pattern = (config_dir / f"{calendar}.pattern").read_text().strip()
    replacement = (config_dir / f"{calendar}.replacement").read_text().strip()

    content = httpx.get(url).text
    unfolded = re.sub(r"\r\n[ \t]", "", content)
    renamed = re.sub(pattern, replacement, unfolded, flags=re.MULTILINE)
    all_day = re.sub(r"^(DTSTART|DTEND)[^:]*:(\d{8})T[\dZ]+$", r"\1;VALUE=DATE:\2", renamed, flags=re.MULTILINE)

    return all_day, 200, {"Content-Type": "text/calendar; charset=utf-8"}
