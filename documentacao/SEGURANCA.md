# Segurança

- Segredos ficam no `.env`, fora do Git.
- `Chave auditoria_cge.txt` está no `.gitignore` e não deve ser versionado.
- PostgreSQL e Redis não publicam porta no host.
- CSRF, cookies `HttpOnly` e `X-Frame-Options: DENY` estão ativos.
- Com `DEBUG=False`, os cookies de sessão e CSRF passam a exigir HTTPS.
- O redirecionamento HTTPS e o endurecimento final ficam na Onda 10, para não impedir o uso local em HTTP.
- Falhas de login gravam apenas o nome de usuário informado, nunca a senha.
- Registros de auditoria não podem ser alterados nem apagados pela administração técnica.

O `.env.example` contém somente placeholders. Senhas e chaves efetivas ficam no `.env`.
