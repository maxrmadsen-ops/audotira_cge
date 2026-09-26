# Arquitetura — Onda 0

A raiz do repositório é o workspace local. O remoto chama-se `audotira_cge`.

```text
aplicacao/
  configuracao/     Django, Celery, URLs
  usuarios/         autenticação e perfis
  auditoria/        trilha de eventos
  painel/           interface, saúde e navegação
  prestacoes_contas/ documentos/ entidades/ extracao/
  normas/ regras/ analises/ evidencias/ achados/
  pareceres/ revisao_humana/ avaliacao/
  inteligencia_artificial/ finops/ administracao/
docker/ nginx/ scripts/ documentacao/ dados_exemplo/ testes/
```

Os pacotes além de `configuracao`, `usuarios`, `auditoria` e `painel` estão reservados. Ainda não têm modelos nem regras de negócio.

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
