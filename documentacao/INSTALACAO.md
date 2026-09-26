# Instalação

Requisitos no servidor de demonstração: Linux Ubuntu, Docker Engine e o plugin Docker Compose. O Python do host não é necessário.

## Linux

```bash
bash instala.sh
```

O script é idempotente na medida do possível. Ele verifica Docker, cria `.env` se faltar, valida variáveis, constrói as imagens, sobe o PostgreSQL, aguarda o healthcheck, habilita pgvector, sobe Redis, Celery, a aplicação e o Nginx, e encerra com um healthcheck HTTP.

As migrações, o `collectstatic` e os usuários iniciais rodam na entrada do container `cge_web`.

## Windows com Docker Desktop

A arquitetura continua Linux. Use Git Bash:

```bash
"C:\Program Files\Git\bin\bash.exe" instala.sh
```

Não execute `instala.sh` pelo PowerShell.

## Variáveis

Copie `.env.example` para `.env`. O script faz isso quando `.env` não existe. Preencha senhas e, nas ondas futuras, as chaves de API. O arquivo `.env` não entra no Git.

Não copie chaves de arquivos soltos para arquivos versionáveis.

## Verificação manual

```bash
docker compose config
docker compose ps
docker compose exec -T cge_banco psql -U cge -d cge -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
docker compose exec -T cge_web python manage.py check
docker compose exec -T cge_web python manage.py test
```

Substitua usuário e banco pelos valores do `.env` se tiver alterado os padrões de desenvolvimento.
