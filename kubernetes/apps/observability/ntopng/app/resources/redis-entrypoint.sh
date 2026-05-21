#!/bin/sh
set -eu

redis-server --save "" --appendonly no &
pid=$!

until redis-cli ping >/dev/null 2>&1; do
  sleep 1
done

redis-cli SET ntopng.prefs.oidc.enabled "1"
redis-cli SET ntopng.prefs.oidc.client_id "${OIDC_CLIENT_ID}"
redis-cli SET ntopng.prefs.oidc.client_secret "${OIDC_CLIENT_SECRET}"
redis-cli SET ntopng.prefs.oidc.issuer_url "https://id.zebernst.dev"
redis-cli SET ntopng.prefs.oidc.base_redirect_uri "https://netflow.zebernst.dev"
redis-cli SET ntopng.prefs.oidc.scopes "openid profile email groups"
redis-cli SET ntopng.prefs.oidc.group_claim "groups"
redis-cli SET ntopng.prefs.oidc.admin_group "${OIDC_ADMIN_GROUP:-ntopng-admins}"
redis-cli SET ntopng.prefs.oidc.auto_create_users "1"

wait "$pid"
