# Changelog

## Onda 2 — 2026-09-26

Gestão e inteligência documental sem LLM: upload protegido, SHA-256, extração nativa, OCR local apenas quando a página não tem texto utilizável, classificação heurística, validação humana e metadados candidatos rastreáveis.

## Onda 1 — 2026-09-26

Modelo canônico da prestação de contas, separando o pactuado do executado.

Inclui entidades, instrumento, plano de trabalho, prestações parciais, execução financeira, linha do tempo, cadastro autenticado, API de consulta e cenário sintético `DEMO-2024-001`.

Não inclui documentos, OCR, normas, regras, IA, evidências, achados, pré-análise, Ground Truth nem FinOps.

## Onda 0 — 2026-09-26

Fundação containerizada: Django, PostgreSQL com pgvector, Redis, Celery worker, Celery Beat, Gunicorn e Nginx.

Inclui autenticação, perfis Administrador, Auditor, Analista e Consulta, painel sem dados de negócio, saúde do sistema e trilha de auditoria de autenticação.

O `.env.example` guarda apenas placeholders. Credenciais efetivas permanecem no `.env` local.

Não inclui domínio da prestação, documentos, normas, regras, IA, evidências, achados, pré-análise, Ground Truth, avaliação ou FinOps.
