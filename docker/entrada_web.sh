#!/bin/sh
set -eu

echo "Aplicando migrações..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "Preparando usuários iniciais..."
python manage.py criar_usuarios_iniciais

echo "Iniciando Gunicorn..."
exec gunicorn aplicacao.configuracao.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
