# Deploy no servidor Linux

Este documento descreve a instalação futura da aplicação já publicada no GitHub.
Nenhuma etapa abaixo deve ser executada sem autorização explícita.

## Caminho

```text
NOTEBOOK/CURSOR → GITHUB → SERVIDOR LINUX → DOCKER COMPOSE → PORTAINER → ACESSO REMOTO
```

O servidor já executa Docker, Portainer e outros projetos. O deploy da CGE entra
em um diretório, uma rede, volumes e uma porta próprios. Os demais ambientes
permanecem intocados.

## Antes de instalar

1. No servidor, execute somente a inspeção:

   ```bash
   bash scripts/inspecionar_servidor.sh 8003
   ```

2. A porta HTTP desta aplicação no Linux é `8003`. As portas `8001`, `8002` e
   `8443` pertencem a outros projetos e constam em `/max/portas.txt`.
3. O diretório de instalação é `/max/auditoria_cge`.
   Não reutilize `/max/sales_opps` nem `/max/analise_juridica`.
4. O arquivo `Chave auditoria_cge.txt` e o `.env` do notebook não vão para o
   servidor. As chaves de modelo de linguagem ainda não são usadas.

## Instalação isolada

No servidor, como usuário autorizado a usar Docker:

```bash
sudo mkdir -p /max/auditoria_cge
sudo chown "$USER":"$USER" /max/auditoria_cge
git clone https://github.com/maxrmadsen-ops/audotira_cge.git /max/auditoria_cge
cd /max/auditoria_cge
git checkout onda-2-concluida
cp .env.example .env
```

Edite o `.env` somente no servidor:

- `DEBUG=False`;
- `SECRET_KEY` nova, diferente da do notebook;
- `DB_PASSWORD` nova;
- senhas novas para administrador, auditor, analista e consulta;
- `ALLOWED_HOSTS`, `DOMINIO` e `CSRF_TRUSTED_ORIGINS` com o endereço real de acesso;
- `NGINX_HTTP_PORT=8003`.

O projeto Compose já se chama `cge`. Mantenha esse nome. Não altere o nome de
outro stack no Portainer e não execute `docker compose down` fora deste
diretório.

Suba apenas este projeto:

```bash
docker compose up -d --build
docker compose ps
```

PostgreSQL e Redis permanecem sem porta publicada no host. O Nginx publica
somente `NGINX_HTTP_PORT`.

## Portainer

O Portainer já em execução deve apenas enxergar o projeto `cge`. Não recrie,
não remova e não altere stacks, containers, redes ou volumes dos outros
ambientes.

Se o stack for criado pela interface, aponte-o exclusivamente para
`/max/auditoria_cge/docker-compose.yml` e para o `.env` desse diretório.
O nome do stack deve ser `cge`.

## Acesso remoto

O acesso inicial é `http://<servidor>:<NGINX_HTTP_PORT>/`. O certificado e o
endurecimento completo continuam previstos para a Onda 10. Até lá, não exponha
a aplicação além da rede autorizada.

## O que não fazer

- Não copiar `.env`, banco, `media/`, `arquivos/` ou documentos do notebook.
- Não publicar as portas 5432 e 6379.
- Não usar `docker system prune`, `docker volume prune` ou `docker compose down`
  sem limitar o comando a este projeto e sem autorização.
- Não fazer force push e não reaproveitar a senha ou a `SECRET_KEY` de desenvolvimento.
