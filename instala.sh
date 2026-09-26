#!/usr/bin/env bash
# Instalação idempotente da fundação CGE.
# Pensado para Linux/Ubuntu e Git Bash. Não grava segredos no repositório.
set -euo pipefail

cd "$(dirname "$0")"

log() {
  printf '%s\n' "$1"
}

falhar() {
  printf 'Erro: %s\n' "$1" >&2
  exit 1
}

exigir_comando() {
  command -v "$1" >/dev/null 2>&1 || falhar "Comando obrigatório ausente: $1"
}

valor_env() {
  local nome="$1"
  grep -E "^${nome}=" .env | head -n 1 | cut -d= -f2- | tr -d '\r'
}

exigir_variavel() {
  local nome="$1"
  local valor
  valor="$(valor_env "$nome")"
  if [ -z "${valor}" ]; then
    falhar "Variável obrigatória ausente ou vazia no .env: ${nome}"
  fi
}

aguardar_container() {
  local nome="$1"
  local estado=""
  local i
  for i in $(seq 1 60); do
    estado="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$nome" 2>/dev/null || true)"
    if [ "$estado" = "healthy" ]; then
      log "${nome}: saudável"
      return 0
    fi
    sleep 2
  done
  falhar "Tempo esgotado aguardando ${nome}. Último estado: ${estado:-ausente}"
}

log "Verificando Docker e Docker Compose..."
exigir_comando docker
docker info >/dev/null 2>&1 || falhar "O Docker não está em execução."
docker compose version >/dev/null 2>&1 || falhar "Docker Compose plugin não encontrado. Use 'docker compose'."

if [ ! -f .env ]; then
  log "Criando .env a partir de .env.example..."
  cp .env.example .env
fi

for variavel in \
  SECRET_KEY DEBUG ALLOWED_HOSTS \
  DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT \
  REDIS_URL CSRF_TRUSTED_ORIGINS NGINX_HTTP_PORT \
  USUARIO_ADMIN USUARIO_ADMIN_SENHA \
  USUARIO_AUDITOR USUARIO_AUDITOR_SENHA \
  USUARIO_ANALISTA USUARIO_ANALISTA_SENHA \
  USUARIO_CONSULTA USUARIO_CONSULTA_SENHA
do
  exigir_variavel "$variavel"
done

for segredo in SECRET_KEY DB_PASSWORD USUARIO_ADMIN_SENHA USUARIO_AUDITOR_SENHA USUARIO_ANALISTA_SENHA USUARIO_CONSULTA_SENHA; do
  valor="$(valor_env "$segredo")"
  case "$valor" in
    altere_esta_senha|altere_esta_chave)
      falhar "Substitua o placeholder de ${segredo} no .env antes de instalar."
      ;;
  esac
done

log "Validando docker compose config..."
docker compose config --quiet

log "Construindo imagens..."
docker compose build

log "Iniciando PostgreSQL..."
docker compose up -d cge_banco
aguardar_container cge_banco

log "Habilitando pgvector..."
DB_USER_VALOR="$(valor_env DB_USER)"
DB_NAME_VALOR="$(valor_env DB_NAME)"
docker compose exec -T cge_banco psql -v ON_ERROR_STOP=1 -U "$DB_USER_VALOR" -d "$DB_NAME_VALOR" -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec -T cge_banco psql -tAc "SELECT extname || ' ' || extversion FROM pg_extension WHERE extname = 'vector';" -U "$DB_USER_VALOR" -d "$DB_NAME_VALOR"

log "Iniciando Redis..."
docker compose up -d cge_redis
aguardar_container cge_redis

log "Iniciando aplicação, worker, agendador e Nginx..."
docker compose up -d cge_web cge_worker cge_agendador cge_nginx
aguardar_container cge_web
aguardar_container cge_worker
aguardar_container cge_agendador
aguardar_container cge_nginx

PORTA="$(valor_env NGINX_HTTP_PORT)"
log "Healthcheck final da aplicação..."
curl -fsS "http://127.0.0.1:${PORTA}/saude/viva/"
printf '\n'

log "Containers:"
docker compose ps

log "Fundação disponível em http://127.0.0.1:${PORTA}/"
log "Usuários iniciais: valores de USUARIO_ADMIN, USUARIO_AUDITOR, USUARIO_ANALISTA e USUARIO_CONSULTA no .env."
log "As senhas correspondentes também estão apenas no .env. Altere-as antes de expor o ambiente."
