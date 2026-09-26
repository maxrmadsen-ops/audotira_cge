# Testes

Os testes da fundação ficam junto aos aplicativos e rodam dentro do container, contra PostgreSQL:

```bash
docker compose exec -T cge_web python manage.py test
docker compose exec -T cge_web python manage.py check
```

Cobertura desta onda:

- perfis e permissões de execução, validação e administração
- login, falha de login e trilha sem senha
- bloqueio de administração e saúde para o perfil Consulta
- painel sem dados fictícios e sem o caso real
- extensão pgvector
- sonda `/saude/viva/`
- estados “Não configurado” para OpenAI e Anthropic

Chamadas reais a APIs de modelo não fazem parte dos testes.
