# Operação do MVP

## Serviços

| Serviço | Função | Volume |
|---|---|---|
| cge_nginx | entrada da stack, publicada em 8003; o HTTPS oficial termina no Nginx do host | estáticos em `cge_static` |
| cge_web | Django/Gunicorn, migrate e collectstatic na subida | `cge_static`, `cge_arquivos`, `cge_midia` |
| cge_worker | Celery worker | `cge_arquivos` |
| cge_agendador | Celery Beat, agenda em arquivo | `cge_celery_agenda` |
| cge_banco | PostgreSQL 16 + pgvector | `cge_postgres_dados` |
| cge_redis | broker, AOF ligado | `cge_redis_dados` |

Reiniciar não apaga volume. O comando proibido na operação normal é `docker compose down -v`.

## Celery

A tarefa periódica `painel.verificar_operacionalidade` só escreve um log. Não dispara análise, extração nem chamada de modelo. O Beat grava a agenda em `/app/celery/agenda`, no volume persistente, então um restart não reposiciona o relógio para o início e não reexecuta o ciclo já marcado. O worker confirma a tarefa ao recebê-la. Uma queda no meio da tarefa periódica perde aquela execução de log; não duplica uma análise, porque essa tarefa não analisa.

## Saúde

A tela do administrador mostra aplicação com versão, migrations, PostgreSQL, Redis, worker, fila, armazenamento e provedores. Celery Beat permanece “Não verificado”: a tela não consulta o processo do agendador e não finge que ele está verde. Migrations pendentes aparecem como Pendente. Falha de leitura aparece como Não disponível ou Indisponível, conforme o componente.

## Checklist de homologação

- [ ] login
- [ ] perfis
- [ ] processos
- [ ] documentos
- [ ] normas
- [ ] regras
- [ ] RAG
- [ ] evidências
- [ ] achados
- [ ] pré-análise
- [ ] revisão humana
- [ ] Ground Truth
- [ ] avaliação
- [ ] IA × Técnico
- [ ] Central Analítica
- [ ] FinOps
- [ ] saúde
- [ ] auditoria
- [ ] backup
- [ ] restore
- [ ] logs
- [ ] persistência
- [ ] segurança
- [ ] rollback

## Rollback

1. Parar somente web, worker e agendador.
2. Voltar o Compose para a imagem `cge_aplicacao:onda9`.
3. Recriar esses três serviços sem remover volumes.
4. Não reverter migration: a Onda 10 não adicionou nenhuma.
5. Smoke de `/saude/viva/` e do login.

Executar o rollback só se a release candidata falhar. Não executá-lo como parte desta preparação.
