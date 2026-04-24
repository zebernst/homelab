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

    # Unfold ICS line continuations (RFC 5545: CRLF + space/tab)
    unfolded = re.sub(r"\r\n[ \t]", "", content)
    renamed = re.sub(pattern, replacement, unfolded, flags=re.MULTILINE)

    return renamed, 200, {"Content-Type": "text/calendar; charset=utf-8"}
