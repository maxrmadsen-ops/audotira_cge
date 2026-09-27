# Changelog

## Onda 7 — 2026-09-27

Pré-análise técnica assistida por IA, versionada e rastreável. A redação usa fatos já apurados e segue a cadeia LLM, validação estrutural, completude, proveniência, guardrails, revisão humana e congelamento. Resposta vazia não é sucesso. Congelamento gera hash SHA-256. A exportação é HTML. PDF, comparação com gabarito, normalização de código ou valor citado pelo modelo e o painel FinOps ficam para as ondas seguintes.

## Onda 6 — 2026-09-27

Evidências e achados potenciais rastreáveis. O resultado da regra não vira achado sozinho. A consolidação usa âncora estruturada, a materialidade é Decimal, e a confirmação é humana. A IA permanece desligada por padrão e não escolhe norma nem confirma achado.

`RevisaoAchado` é decisão operacional humana e não constitui Ground Truth. Tempo médio de revisão e score numérico ficam para ondas posteriores.

Não inclui a pré-análise técnica final, Ground Truth nem o painel FinOps.

## Onda 5 — 2026-09-27

Camada de IA com provedores OpenAI e Anthropic isolados em adaptadores, provedor simulado para a suíte, agentes por regra que requer IA, prompts versionados, preços administráveis, registro de tokens, latência e custo estimado, validação de schema e de fontes, fallback auditado e laboratório que não altera a execução oficial. A integração do motor nasce desligada. Nenhuma chamada paga entra na suíte.

Não inclui achado definitivo, pré-análise final, Ground Truth, comparação IA × técnico nem o painel FinOps.

## Onda 4 — 2026-09-26

Catálogo e motor das 89 regras da matriz técnica. Executores determinísticos usam `Decimal`. Regras semânticas ficam pendentes de IA. Ausência de dado não vira divergência. O teste cego exclui relatório com análise técnica prévia. A síntese da rodada não conclui a prestação.

Não inclui modelo generativo, evidência definitiva, achado, pré-análise, Ground Truth nem FinOps.

## Onda 3 — 2026-09-26

Base normativa e RAG rastreável. A vigência e a aplicabilidade escolhem as normas antes da busca lexical, vetorial ou híbrida. Embeddings de teste usam um provedor simulado, sem chamada de rede. Não há motor de regras nem modelo generativo.

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
