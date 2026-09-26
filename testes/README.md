# Testes

A suíte executável está nos aplicativos Django (`aplicacao/usuarios/tests.py`, `aplicacao/auditoria/tests.py`, `aplicacao/painel/tests.py`).

Comando:

```bash
docker compose exec -T cge_web python manage.py test
```

Veja também [TESTES.md](../documentacao/TESTES.md).
