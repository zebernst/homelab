import re

import httpx


def _fetch(url: str) -> str:
    content = httpx.get(url).text
    return re.sub(r"\r\n[ \t]", "", content)


def jsm_on_call(url: str) -> str:
    ical = _fetch(url)
    ical = re.sub(r"^SUMMARY:.*$", "SUMMARY:SmarterDx: On Call", ical, flags=re.MULTILINE)
    ical = re.sub(r"^(DTSTART|DTEND)[^:]*:(\d{8})T[\dZ]+$", r"\1;VALUE=DATE:\2", ical, flags=re.MULTILINE)
    return ical
