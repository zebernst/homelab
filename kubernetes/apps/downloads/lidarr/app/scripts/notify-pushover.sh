#!/usr/bin/env bash
set -Eeuo pipefail

# User defined variables for pushover
PUSHOVER_USER_KEY="${PUSHOVER_USER_KEY:-required}"
PUSHOVER_TOKEN="${PUSHOVER_TOKEN:-required}"
PUSHOVER_PRIORITY="${PUSHOVER_PRIORITY:-"-2"}"

if [[ "${lidarr_eventtype:-}" == "Test" ]]; then
    PUSHOVER_PRIORITY="1"
    printf -v PUSHOVER_TITLE \
        "Test Notification"
    printf -v PUSHOVER_MESSAGE \
        "Howdy this is a test notification from %s" \
            "${lidarr_instancename:-Lidarr}"
    printf -v PUSHOVER_URL \
        "%s" \
            "${lidarr_applicationurl:-localhost}"
    printf -v PUSHOVER_URL_TITLE \
        "Open %s" \
            "${lidarr_instancename:-Lidarr}"
fi

if [[ "${lidarr_eventtype:-}" == "AlbumDownload" ]]; then
    printf -v PUSHOVER_TITLE \
        "Album %s" \
            "$( [[ "${lidarr_isupgrade}" == "True" ]] && echo "Upgraded" || echo "Imported" )"
    printf -v PUSHOVER_MESSAGE \
        "<b>%s (%s) [%s]</b><small>\n%s</small><small>\n<b>Client:</b> %s</small>" \
            "${lidarr_artist_name}" \
            "${lidarr_album_releasedate}" \
            "${lidarr_album_title}" \
            "${lidarr_album_overview}" \
            "${lidarr_download_client:-Unknown}"
    printf -v PUSHOVER_URL \
        "%s/album/%s" \
            "${lidarr_applicationurl:-localhost}" "${lidarr_artist_mbid}"
    printf -v PUSHOVER_URL_TITLE \
        "View album in %s" \
            "${lidarr_instancename:-Lidarr}"
fi

json_data=$(jo \
    token="${PUSHOVER_TOKEN}" \
    user="${PUSHOVER_USER_KEY}" \
    title="${PUSHOVER_TITLE}" \
    message="${PUSHOVER_MESSAGE}" \
    url="${PUSHOVER_URL}" \
    url_title="${PUSHOVER_URL_TITLE}" \
    priority="${PUSHOVER_PRIORITY}" \
    html="1"
)

status_code=$(curl \
    --silent \
    --write-out "%{http_code}" \
    --output /dev/null \
    --request POST  \
    --header "Content-Type: application/json" \
    --data-binary "${json_data}" \
    "https://api.pushover.net/1/messages.json" \
)

printf "pushover notification returned with HTTP status code %s and payload: %s\n" \
    "${status_code}" \
    "$(echo "${json_data}" | jq --compact-output)" >&2
