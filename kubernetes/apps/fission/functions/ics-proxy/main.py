from pathlib import Path

import calendars
import logging

from fastapi import Request
from fastapi.responses import Response

logger = logging.getLogger("ics-proxy")


async def main(request: Request) -> Response:
    body = await request.body()
    logger.debug("headers=%s body=%s", dict(request.headers), body.decode())

    calendar = request.query_params.get("calendar")
    if not calendar:
        return Response(content="Missing ?calendar= query parameter", status_code=400)

    secret_dir = next(Path("/secrets/fission").iterdir())

    token = request.query_params.get("token")
    expected_token = (secret_dir / "token").read_text().strip()
    if not token or token != expected_token:
        logger.warning("unauthorized request for calendar=%s", calendar)
        return Response(content="Unauthorized", status_code=401)

    logger.info("processing calendar=%s", calendar)

    match calendar:
        case "on-call":
            url = (secret_dir / "on-call.url").read_text().strip()
            result = calendars.jsm_on_call(url)
        case _:
            return Response(content=f"Unknown calendar: {calendar}", status_code=404)

    logger.info("done calendar=%s bytes=%d", calendar, len(result))
    return Response(content=result, media_type="text/calendar; charset=utf-8")
