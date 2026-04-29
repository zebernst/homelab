from pathlib import Path
import re

import httpx


def main() -> tuple[str, int, dict[str, str]]:
    secret_dir = next(Path("/secrets/fission").iterdir())
    config_dir = next(Path("/configs/fission").iterdir())

    url = (secret_dir / "upstream-url").read_text().strip()
    pattern = (config_dir / "summary-pattern").read_text().strip()
    replacement = (config_dir / "summary-replacement").read_text().strip()

    content = httpx.get(url).text

    unfolded = re.sub(r"\r\n[ \t]", "", content)
    renamed = re.sub(pattern, replacement, unfolded, flags=re.MULTILINE)
    all_day = re.sub(r"^(DTSTART|DTEND)[^:]*:(\d{8})T[\dZ]+$", r"\1;VALUE=DATE:\2", renamed, flags=re.MULTILINE)

    return all_day, 200, {"Content-Type": "text/calendar; charset=utf-8"}
