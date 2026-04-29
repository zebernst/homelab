import re
from datetime import datetime, timedelta

import httpx


def _fetch(url: str) -> str:
    content = httpx.get(url).text
    return re.sub(r"\r\n[ \t]", "", content)


def _to_all_day_inclusive(m: re.Match) -> str:
    field, date_str = m.group(1), m.group(2)
    date = datetime.strptime(date_str, "%Y%m%d")
    if field == "DTEND":
        date += timedelta(days=1)
    return f"{field};VALUE=DATE:{date:%Y%m%d}"


def jsm_on_call(url: str) -> str:
    ical = _fetch(url)
    ical = re.sub(r"^SUMMARY:.*$", "SUMMARY:Platform: On Call", ical, flags=re.MULTILINE)
    ical = re.sub(r"^(DTSTART|DTEND)[^:]*:(\d{8})T[\dZ]+$", _to_all_day_inclusive, ical, flags=re.MULTILINE)
    return ical
