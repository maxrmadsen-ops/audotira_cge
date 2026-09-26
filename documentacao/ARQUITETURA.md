# Arquitetura — Onda 3

A raiz do repositório é o workspace local. O remoto chama-se `audotira_cge`.

```text
aplicacao/
  configuracao/     Django, Celery, URLs
  usuarios/         autenticação e perfis
  auditoria/        trilha de eventos
  painel/           interface, saúde e navegação
  prestacoes_contas/ documentos/ entidades/
  normas/           base normativa, vigência e RAG
  regras/ analises/ evidencias/ achados/
  pareceres/ revisao_humana/ avaliacao/
  inteligencia_artificial/ finops/ administracao/
docker/ nginx/ scripts/ documentacao/ dados_exemplo/ testes/
```

`entidades`, `prestacoes_contas`, `documentos` e `normas` estão ativos. Os demais pacotes continuam reservados.

O pipeline documental está descrito em [Inteligência documental](INTELIGENCIA_DOCUMENTAL.md). A base de conhecimento está em [Base normativa](BASE_NORMATIVA.md) e [RAG normativo](RAG_NORMATIVO.md).

Norma e trecho normativo não são documentos da prestação nem regras de análise. A regra que verificará se um dever ocorreu fica para a Onda 4.

## Modelo de domínio

A prestação aponta para concedente e beneficiário como `Entidade`. O instrumento guarda número, tipo, vigência e valor. Plano, itens e metas representam o previsto. Despesas, documentos fiscais, pagamentos, movimentações, contrapartidas e devoluções representam o executado, com relações muitos-para-muitos onde um lançamento pode ter vários documentos ou pagamentos.

Valores monetários usam `Decimal` com 16 dígitos e 2 casas. Campos ausentes permanecem nulos. A trilha de auditoria registra usuário, ação, entidade e identificador, sem o conteúdo dos campos.

## Containers

| Serviço | Função | Publicação |
|---|---|---|
| cge_banco | PostgreSQL 16 com pgvector | somente rede `cge_rede` |
| cge_redis | broker e resultados do Celery | somente rede `cge_rede` |
| cge_web | Django via Gunicorn | somente rede `cge_rede` |
| cge_worker | Celery worker | somente rede `cge_rede` |
| cge_agendador | Celery Beat | somente rede `cge_rede` |
| cge_nginx | proxy e arquivos estáticos | porta do host, padrão 8080 |

Volumes persistentes: `cge_postgres_dados`, `cge_redis_dados`, `cge_static`, `cge_arquivos`, `cge_midia`, `cge_celery_agenda`.

## Sequência oficial

0 Fundação · 1 Modelo de domínio · 2 Gestão e inteligência documental · 3 Base normativa e RAG · 4 Catálogo e motor de regras · 5 IA multiprovedor e agentes · 6 Evidências e achados · 7 Pré-análise técnica e revisão humana · 8 Ground Truth e avaliação IA × técnico · 9 Governança, FinOps e experiência executiva · 10 Hardening, caso real e preparação da demonstração.

A instrumentação de custo de IA nasce na Onda 5. O painel FinOps fica na Onda 9. A Onda 10 não é absorvida pela Onda 9.

## Fronteiras já definidas

- A camada de negócio não chamará SDKs de LLM diretamente.
- Cálculo determinístico não será delegado a modelo de linguagem.
- Ground Truth ficará no módulo de avaliação e fora do contexto da análise até o congelamento.
- Versões de regra, prompt, norma e preço usadas em análise não serão sobrescritas.
