# Release 1.0.0-rc1

Release candidata do MVP, preparada no notebook em 2026-09-27. Não foi implantada no Linux e não recebeu processo real.

## Identidade

| Campo | Valor |
|---|---|
| Versão | 1.0.0-rc1 |
| Onda | 10 |
| Base | tag `onda-9-concluida`, commit `be83fed7fa8ac52626a35d249cfd5edd225357d1` |
| Imagem | `cge_aplicacao:onda10-rc1` |
| Imagem anterior | `cge_aplicacao:onda9` |
| Banco | PostgreSQL 16 com pgvector, volume `cge_postgres_dados` |
| Broker | Redis 7, volume `cge_redis_dados` |
| Entrada | Nginx 1.27, única porta publicada |

Não usar a tag `:latest`.

## O que esta release não muda

Modelo canônico, pipeline documental, normas, RAG, catálogo de 89 regras, motor, multi-LLM, evidências, achados, proveniência, pré-análise, Ground Truth, avaliação, permissões, hashes, Central Analítica e FinOps permanecem os da Onda 9. O período do filtro continua com Até abaixo de De.

## Migrations

A Onda 10 não cria migration. O plano aplicado continua o da Onda 8 (`avaliacao.0001_initial` e anteriores). Conferir com `python manage.py showmigrations` no container. A tela Saúde marca Migrations como Pendente se houver plano não aplicado, e como Não disponível se a leitura falhar.

## Dependências

As dependências de execução estão em `requirements.txt` e na imagem. A suíte não chama OpenAI nem Anthropic. `IA_INTEGRACAO` permanece `desligada` até autorização.

## Configuração necessária

Copiar `.env.example` para `.env` fora do Git. No Linux, gerar `SECRET_KEY`, `DB_PASSWORD` e senhas de perfil novas. Não reaproveitar os valores do notebook.

Variáveis novas desta onda:

- `COOKIES_SEGUROS=false` enquanto o acesso for HTTP.
- `BEHIND_PROXY=true` no Linux, porque o Nginx é o único ponto de entrada.

## Pendências classificadas

| Pendência | Classe | Decisão nesta onda |
|---|---|---|
| PDF da pré-análise | Desejável para o piloto, não bloqueia homologação | Não implementar. A exportação HTML permanece. |
| Cinco rejeições de proveniência da Onda 7 | Recomendável, não bloqueia homologação | Não alterar o validador. Ver causa abaixo. |
| Preços comerciais dos modelos | Pode permanecer para pós-MVP | Custo continua “Não disponível”. |
| Deploy Linux | Necessário para a entrada em homologação no servidor | Preparado e não executado. |
| Base só com DEMO-2024-001 | Necessário deixar explícito na homologação | Mantido e identificável. Não apagar. |
| Carga de processo real | Necessária só depois do checkpoint 10.2 | Não executar. |

## Proveniência — causa, sem correção aplicada

O validador em `aplicacao/pareceres/validador.py` rejeita valor ou código que não esteja no catálogo estruturado.

- `VALOR = \d+[.,]\d{2}` também casa `000,00` dentro de `1.000,00`. O fragmento não está na lista de números conhecidos e a afirmação é rejeitada.
- `CODIGO = \b[A-Z]{2,4}-\d+\b` também casa `DEMO-2024` dentro de `DEMO-2024-001`.

Regra proposta, ainda não aplicada: o valor monetário brasileiro deve consumir o número inteiro, inclusive os grupos de milhar, e o código deve consumir todos os segmentos numéricos (`DEMO-2024-001`), não só o primeiro. O risco de aplicar agora é aceitar um trecho que hoje é rejeitado de propósito. A correção só entra com testes que cubram `1.000,00`, `000,00` isolado, `DEMO-2024-001` e um código realmente ausente.

## Rollback conceitual

A imagem anterior é `cge_aplicacao:onda9`, no commit `be83fed`. Não há migration nova, então o volume do banco permanece compatível. O rollback troca a tag da imagem e recria web, worker e agendador, sem `down -v`.
