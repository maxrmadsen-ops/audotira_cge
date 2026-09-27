# Deploy no servidor Linux

Este documento é o plano. Nenhuma etapa abaixo deve ser executada sem autorização explícita do checkpoint 10.1. O notebook não implanta o servidor.

## Caminho

```text
NOTEBOOK → GITHUB → RELEASE VERSIONADA → SERVIDOR LINUX → DOCKER COMPOSE
```

Não desenvolver no servidor. O diretório previsto continua `/max/auditoria_cge`. A porta HTTP prevista continua `8003`. Não usar `8001`, `8002` nem `8443`. Não alterar `/max/portas.txt`, Portainer dos outros stacks, nem outro diretório em `/max`.

## O que conferir no servidor, quando autorizado

Sistema, disco, memória, Docker Engine, plugin Compose, a porta 8003 livre e permissão de escrita em `/max/auditoria_cge`. Não há domínio nem certificado definidos. O acesso inicial, se autorizado, é HTTP na rede permitida: `http://<servidor>:8003/`. HTTPS fica para quando existirem nome e certificado; não inventar nenhum dos dois.

## Instalação, quando autorizada

```bash
sudo mkdir -p /max/auditoria_cge
sudo chown "$USER":"$USER" /max/auditoria_cge
git clone https://github.com/maxrmadsen-ops/audotira_cge.git /max/auditoria_cge
cd /max/auditoria_cge
git checkout <commit autorizado da release>
cp .env.example .env
```

Editar o `.env` só no servidor:

- `DEBUG=False`
- `SECRET_KEY` nova
- `DB_PASSWORD` nova
- senhas novas dos quatro perfis
- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` com o endereço real, incluindo a porta
- `NGINX_HTTP_PORT=8003`
- `BEHIND_PROXY=true`
- `COOKIES_SEGUROS=false` até existir HTTPS
- `IA_INTEGRACAO=desligada`

Subir sem apagar volume:

```bash
docker compose up -d --build
docker compose ps
```

A imagem esperada é `cge_aplicacao:onda10-rc1`. PostgreSQL e Redis permanecem sem porta publicada. Se já existir stack `cge` com dados, fazer o backup descrito em `BACKUP_RESTORE.md` antes de recriar containers. Não executar `docker compose down -v`.

## O que não fazer

- Não copiar `.env`, banco, `media/`, `arquivos/` ou documentos do notebook.
- Não publicar 5432 nem 6379.
- Não carregar processo real neste deploy.
- Não chamar OpenAI ou Anthropic sem autorização separada.
- Não fazer force push e não reaproveitar segredo de desenvolvimento.
