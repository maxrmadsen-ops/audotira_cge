# Segurança do MVP

## O que não entra no Git

`.env`, chaves, tokens, senhas, `Authorization`, certificados privados, dumps, PDFs reais, planilhas reais e `Insumos Piloto/`. O `.env.example` só tem placeholders.

## Ambiente

O notebook pode usar `DEBUG=True` e HTTP em `127.0.0.1:8080`.

O Linux usa `DEBUG=False`. `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` recebem o endereço real de acesso, sem curinga. `SECRET_KEY` e `DB_PASSWORD` são novas e diferentes das do notebook.

No Linux homologado, o acesso oficial é `https://cge.datapedia.ia.br`. `COOKIES_SEGUROS=true` e `BEHIND_PROXY=true`. O Nginx do host termina o TLS e envia `X-Forwarded-Proto: https`. O cookie de sessão é Secure, HttpOnly e SameSite Lax. HSTS permanece desligado. A porta 8003 continua técnica; com cookie Secure, o login oficial é o HTTPS. O certificado não entra no Git. O procedimento está em `HTTPS_DNS.md`.

## Rede

Só o Nginx publica porta no host. No notebook, `NGINX_HTTP_PORT=8080`. No Linux, `8003`. PostgreSQL e Redis não têm `ports:` no Compose. A rede é `cge_rede`.

O Nginx não envia a versão no header (`server_tokens off`). O corpo de upload está limitado a 25 MB na borda e a 20 MB no Django.

## Logs

Log operacional: serviço, horário, nível, nome do logger e mensagem curta. A trilha de auditoria continua no banco, sem senha e sem corpo de documento.

Não registrar senha, chave de API, `Authorization`, documento completo, CPF, Ground Truth sigiloso, prompt com dado protegido, resposta integral sensível nem chain-of-thought. Erro de produção não devolve stack trace ao navegador quando `DEBUG=False`.

## Permissões

Consulta lê. Analista colabora no que as ondas anteriores permitiram. Auditor tem a autoridade técnica já implementada, inclusive congelar Ground Truth e avaliação. Administrador administra a plataforma e não congela Ground Truth nem avaliação. Esta onda não altera essas regras.

## IA

A suíte e a subida do ambiente não chamam OpenAI nem Anthropic. Provedor sem chave ou desabilitado aparece como Não configurado. A saúde não faz chamada ao modelo.
