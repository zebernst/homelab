import urllib.request
import re


def main():
    with open("/secrets/fission/ics-proxy-secret/upstream-url") as f:
        url = f.read().strip()

    with urllib.request.urlopen(url) as resp:
        content = resp.read().decode("utf-8")

    # Unfold ICS line continuations (RFC 5545: CRLF + space/tab)
    unfolded = re.sub(r"\r\n[ \t]", "", content)
    renamed = re.sub(r"(?m)^SUMMARY:.*$", "SUMMARY:On Call", unfolded)

    return renamed, 200, {"Content-Type": "text/calendar; charset=utf-8"}
