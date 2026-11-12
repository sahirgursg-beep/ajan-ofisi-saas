#!/usr/bin/env bash
# GitHub'daki son surumu VPS'e alir. GitHub Actions her 'main' guncellemesinde bunu calistirir.
set -euo pipefail
cd /opt/ajan-ofisi
eski=$(git rev-parse HEAD)
git fetch -q origin main && git reset -q --hard origin/main
yeni=$(git rev-parse HEAD)
docker compose --env-file .env -f deploy/vps/docker-compose.yml up -d --build --remove-orphans
docker image prune -f >/dev/null
for i in $(seq 1 30); do
  if docker compose --env-file .env -f deploy/vps/docker-compose.yml exec -T web python -c \
      "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/saglik')" 2>/dev/null; then
    echo "Guncellendi: ${eski:0:7} -> ${yeni:0:7}"; exit 0
  fi
  sleep 4
done
echo "UYARI: web servisi saglik kontrolunden gecmedi, onceki surume donuluyor"
git reset -q --hard "$eski"
docker compose --env-file .env -f deploy/vps/docker-compose.yml up -d --build
exit 1
