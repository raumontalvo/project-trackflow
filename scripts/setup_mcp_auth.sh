#!/usr/bin/env bash

set -euo pipefail

KEYCLOAK_CONTAINER="${KEYCLOAK_CONTAINER:-trackflow-keycloak}"
KEYCLOAK_SERVER="${KEYCLOAK_SERVER:-http://localhost:8080}"
REALM="trackflow"
CLIENT_ID="trackflow-mcp-client"
MCP_AUDIENCE="${MCP_RESOURCE_URL:-http://localhost:8001}"

KCADM="/opt/keycloak/bin/kcadm.sh"

echo "Configuring TrackFlow MCP OAuth..."

docker exec "$KEYCLOAK_CONTAINER" \
  "$KCADM" config credentials \
  --server "$KEYCLOAK_SERVER" \
  --realm master \
  --user admin \
  --password admin

if ! docker exec "$KEYCLOAK_CONTAINER" \
  "$KCADM" get "realms/$REALM" >/dev/null 2>&1; then

  docker exec "$KEYCLOAK_CONTAINER" \
    "$KCADM" create realms \
    -s realm="$REALM" \
    -s enabled=true \
    -s displayName="TrackFlow"
fi

for scope in "incidents:read" "incidents:write" "inventory:read"; do
  existing_scope_id=$(
    docker exec "$KEYCLOAK_CONTAINER" \
      "$KCADM" get client-scopes \
      -r "$REALM" \
      -q name="$scope" \
      --fields id \
    | python -c \
      'import json,sys; data=json.load(sys.stdin); print(data[0]["id"] if data else "")'
  )

  if [ -z "$existing_scope_id" ]; then
    docker exec "$KEYCLOAK_CONTAINER" \
      "$KCADM" create client-scopes \
      -r "$REALM" \
      -s name="$scope" \
      -s protocol=openid-connect
  fi
done

CLIENT_UUID=$(
  docker exec "$KEYCLOAK_CONTAINER" \
    "$KCADM" get clients \
    -r "$REALM" \
    -q clientId="$CLIENT_ID" \
    --fields id \
  | python -c \
    'import json,sys; data=json.load(sys.stdin); print(data[0]["id"] if data else "")'
)

if [ -z "$CLIENT_UUID" ]; then
  docker exec "$KEYCLOAK_CONTAINER" \
    "$KCADM" create clients \
    -r "$REALM" \
    -s clientId="$CLIENT_ID" \
    -s enabled=true \
    -s publicClient=false \
    -s serviceAccountsEnabled=true \
    -s standardFlowEnabled=true \
    -s directAccessGrantsEnabled=false \
    -s 'redirectUris=["http://localhost:*"]' \
    -s 'webOrigins=["http://localhost:*"]'

  CLIENT_UUID=$(
    docker exec "$KEYCLOAK_CONTAINER" \
      "$KCADM" get clients \
      -r "$REALM" \
      -q clientId="$CLIENT_ID" \
      --fields id \
    | python -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])'
  )
fi

for scope in "incidents:read" "incidents:write" "inventory:read"; do
  SCOPE_ID=$(
    docker exec "$KEYCLOAK_CONTAINER" \
      "$KCADM" get client-scopes \
      -r "$REALM" \
      -q name="$scope" \
      --fields id \
    | python -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])'
  )

  docker exec "$KEYCLOAK_CONTAINER" \
    "$KCADM" update \
    "clients/$CLIENT_UUID/optional-client-scopes/$SCOPE_ID" \
    -r "$REALM" >/dev/null 2>&1 || true
done

MAPPER_ID=$(
  docker exec "$KEYCLOAK_CONTAINER" \
    "$KCADM" get \
    "clients/$CLIENT_UUID/protocol-mappers/models" \
    -r "$REALM" \
  | python -c \
    'import json,sys; data=json.load(sys.stdin); print(next((x["id"] for x in data if x["name"]=="trackflow-mcp-audience"), ""))'
)

if [ -z "$MAPPER_ID" ]; then
  docker exec "$KEYCLOAK_CONTAINER" \
    "$KCADM" create \
    "clients/$CLIENT_UUID/protocol-mappers/models" \
    -r "$REALM" \
    -s name=trackflow-mcp-audience \
    -s protocol=openid-connect \
    -s protocolMapper=oidc-audience-mapper \
    -s "config.\"included.custom.audience\"=\"$MCP_AUDIENCE\"" \
    -s 'config."id.token.claim"="false"' \
    -s 'config."access.token.claim"="true"'
fi

echo
echo "TrackFlow MCP OAuth configured."
echo "Realm: $REALM"
echo "Client: $CLIENT_ID"
echo "Issuer: http://localhost:9000/realms/$REALM"
echo
echo "Client secret is intentionally not printed."
echo "Retrieve it locally with kcadm and store it in your ignored .env file."
