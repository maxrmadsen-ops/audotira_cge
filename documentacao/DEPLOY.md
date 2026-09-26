# Deploy

Ambiente alvo: Ubuntu com Docker Compose.

```bash
bash instala.sh
```

Antes de um ambiente compartilhado:

1. Defina `DEBUG=False`.
2. Troque `SECRET_KEY`, `DB_PASSWORD` e as senhas dos usuários.
3. Ajuste `ALLOWED_HOSTS`, `DOMINIO` e `CSRF_TRUSTED_ORIGINS` para a origem HTTPS.
4. Mantenha PostgreSQL e Redis sem porta publicada.
5. Coloque um certificado na frente do Nginx. O endurecimento completo é a Onda 10.

Não publique o arquivo `.env` nem volumes do banco.
