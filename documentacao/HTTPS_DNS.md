# DNS e HTTPS

A URL oficial da homologação é `https://cge.datapedia.ia.br`.

O nome `cge.datapediaia.br`, sem o ponto entre datapedia e ia, não existe no DNS público. O registro que resolve é:

| Campo | Valor |
|---|---|
| Nome | `cge.datapedia.ia.br` |
| Tipo | A |
| IPv4 | `2.25.228.117` |
| Emissor | Let's Encrypt |
| Validade | 27 set 2026 a 26 dez 2026 |
| Renovação | `certbot` no host, com reload do Nginx após a renovação |

## Arquitetura

A internet chega ao Nginx do sistema, que já escuta 80 e 443 para os outros serviços. A CGE não abre um segundo processo nessas portas.

```text
https://cge.datapedia.ia.br:443
        ↓
Nginx do host
        ↓
http://127.0.0.1:8003
        ↓
Nginx da stack cge
        ↓
cge_web
```

A porta 8003 continua publicada como acesso técnico. O acesso oficial é o domínio em HTTPS. PostgreSQL e Redis continuam sem porta no host.

O certificado e a chave privada ficam em `/etc/letsencrypt/live/cge.datapedia.ia.br/`. Não entram no Git.

## Cookies e proxy

No `.env` do servidor, fora do Git:

- `DEBUG=False`
- `BEHIND_PROXY=true`
- `COOKIES_SEGUROS=true`
- `ALLOWED_HOSTS` inclui `cge.datapedia.ia.br`, `127.0.0.1` e `localhost` para o healthcheck interno
- `CSRF_TRUSTED_ORIGINS` inclui `https://cge.datapedia.ia.br`

O Nginx do host envia `X-Forwarded-Proto: https`. O Nginx da stack repassa esse valor. O Django só marca o cookie como Secure quando `COOKIES_SEGUROS=true`.

HSTS ainda não foi ligado. Não há preload nem inclusão de subdomínios.

## Resolução do container web

O Nginx da stack resolve `cge_web` pelo DNS interno do Docker (`127.0.0.11`), com `proxy_pass` em variável. Recriar só o `cge_web` não deixa o proxy preso no IP antigo.

## Rollback para a porta 8003

Não usar `docker compose down -v`. Não apagar volumes.

1. Retirar o site `cge` de `/etc/nginx/sites-enabled/` e recarregar o Nginx do host.
2. No `.env` do servidor, voltar `COOKIES_SEGUROS=false`.
3. Recriar somente `cge_web` para reler o ambiente.
4. O acesso técnico volta a ser `http://2.25.228.117:8003`.

O banco, o Redis, os documentos e a mídia permanecem nos volumes.
