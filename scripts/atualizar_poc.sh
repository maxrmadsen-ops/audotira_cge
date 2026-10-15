#!/bin/sh
# Atualiza somente a POC. Recusa o diretório da demonstração.
set -eu
raiz=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
if [ "$raiz" = "/max/auditoria_cge" ]; then
  echo "Recusa: /max/auditoria_cge é a demonstração."
  exit 1
fi
cd "$raiz"
if ! grep -q '^name: cge_poc$' docker-compose.yml; then
  echo "Recusa: o compose deste diretório não é o projeto cge_poc."
  exit 1
fi
git pull --ff-only
docker compose build cge_web
docker compose up -d --no-deps cge_web
i=0
while [ "$i" -lt 30 ]; do
  estado=$(docker inspect --format '{{.State.Health.Status}}' cge_poc_web 2>/dev/null || true)
  if [ "$estado" = "healthy" ]; then
    break
  fi
  i=$((i + 1))
  sleep 5
done
if [ "$estado" != "healthy" ]; then
  echo "cge_poc_web não ficou saudável."
  exit 1
fi
docker compose up -d --no-deps cge_worker cge_agendador
docker compose ps
