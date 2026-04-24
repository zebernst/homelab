import os
import re

import httpx


def main():
    secrets_dir = "/secrets/fission"
    secret_name = next(iter(os.listdir(secrets_dir)))
    secret_path = os.path.join(secrets_dir, secret_name)

    with open(os.path.join(secret_path, "upstream-url")) as f:
        url = f.read().strip()
    with open(os.path.join(secret_path, "summary-pattern")) as f:
        pattern = f.read().strip()
    with open(os.path.join(secret_path, "summary-replacement")) as f:
        replacement = f.read().strip()

    content = httpx.get(url).text

    # Unfold ICS line continuations (RFC 5545: CRLF + space/tab)
    unfolded = re.sub(r"\r\n[ \t]", "", content)
    renamed = re.sub(pattern, replacement, unfolded, flags=re.MULTILINE)

    return renamed, 200, {"Content-Type": "text/calendar; charset=utf-8"}
