# Testes

Os testes da fundação ficam junto aos aplicativos e rodam dentro do container, contra PostgreSQL:

```bash
docker compose exec -T cge_web python manage.py test
docker compose exec -T cge_web python manage.py check
```

A Onda 2 acrescenta testes de upload, MIME, tamanho, SHA-256, duplicidade, permissões, armazenamento, extração nativa, OCR, falha parcial, classificação, correção humana, metadados, Celery, reprocessamento, auditoria e visualização protegida. Os testes das ondas anteriores permanecem na suíte.

A Onda 1 acrescenta testes de entidades, prestação, instrumento, plano, itens, parciais, despesa, documento fiscal, pagamento, movimentação, meta, contrapartida, devolução, `Decimal`, ordenação, permissões, dados incompletos, linha do tempo, auditoria e cenário sintético. Os testes da Onda 0 permanecem na suíte.

Cobertura da fundação:

- perfis e permissões de execução, validação e administração
- login, falha de login e trilha sem senha
- bloqueio de administração e saúde para o perfil Consulta
- painel sem dados fictícios e sem o caso real
- extensão pgvector
- sonda `/saude/viva/`
- estados “Não configurado” para OpenAI e Anthropic

Chamadas reais a APIs de modelo não fazem parte dos testes.
