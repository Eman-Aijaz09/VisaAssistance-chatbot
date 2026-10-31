#!/bin/bash
# App tier bootstrap: install Docker, read secrets from Key Vault via managed identity, start FastAPI.
exec > /var/log/visa-init.log 2>&1
set -x

curl -fsSL https://get.docker.com | sh

mkdir -p /opt/visa
cd /opt/visa

get_secret() {
  local name=$1
  for i in $(seq 1 60); do
    token=$(curl -s -H "Metadata:true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fvault.azure.net" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
    if [ -n "$token" ]; then
      val=$(curl -sf -H "Authorization: Bearer $token" "${vault_uri}secrets/$name?api-version=7.4" | python3 -c 'import sys,json; print(json.load(sys.stdin)["value"])' 2>/dev/null)
      if [ -n "$val" ]; then
        echo "$val"
        return 0
      fi
    fi
    sleep 10
  done
  return 1
}

set +x
printf 'SUPABASE_DB_URL=%s\n' "$(get_secret supabase-db-url)" > .env
printf 'GROQ_API_KEY=%s\n' "$(get_secret groq-api-key)" >> .env
chmod 600 .env
set -x

cat > docker-compose.yml <<'COMPOSE'
services:
  app:
    image: ghcr.io/${ghcr_owner}/visa-app:latest
    env_file: .env
    ports:
      - "8000:8000"
    restart: unless-stopped
COMPOSE

docker compose pull
docker compose up -d
