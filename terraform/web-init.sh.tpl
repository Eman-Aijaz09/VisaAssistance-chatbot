#!/bin/bash
# Web tier bootstrap: install Docker, start nginx + frontend.
# "app" is mapped to the internal load balancer, so the existing nginx.conf (app:8000) works unchanged.
exec > /var/log/visa-init.log 2>&1
set -x

curl -fsSL https://get.docker.com | sh

mkdir -p /opt/visa
cd /opt/visa

cat > docker-compose.yml <<'COMPOSE'
services:
  frontend:
    image: ghcr.io/${ghcr_owner}/visa-frontend:latest
    expose:
      - "3000"
    restart: unless-stopped

  web:
    image: ghcr.io/${ghcr_owner}/visa-web:latest
    ports:
      - "80:80"
    depends_on:
      - frontend
    extra_hosts:
      - "app:${internal_lb_ip}"
    restart: unless-stopped
COMPOSE

docker compose pull
docker compose up -d
