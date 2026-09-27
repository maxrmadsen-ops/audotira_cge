# Backup e restore

Nenhum backup entra no Git. O diretório `backups/` está ignorado. Segredos do `.env` não fazem parte do dump.

Executar no diretório do projeto, com a stack `cge` no ar. Não usar `docker compose down -v`.

## PostgreSQL

Backup:

```bash
mkdir -p backups
docker compose exec -T cge_banco pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > backups/cge_$(date +%Y%m%d_%H%M).dump
```

No PowerShell, definir a data no nome do arquivo antes do redirecionamento. A senha não aparece no comando se `PGPASSWORD` não for ecoado; o `pg_dump` dentro do container usa o usuário já definido no ambiente do serviço.

Restore, somente com autorização e com a aplicação parada para escrita:

```bash
docker compose stop cge_web cge_worker cge_agendador
docker compose exec -T cge_banco pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists < backups/ARQUIVO.dump
docker compose start cge_web cge_worker cge_agendador
```

`--clean` recria objetos do banco nomeado. Não apaga o volume.

## Documentos

Os arquivos do piloto ficam nos volumes nomeados `cge_arquivos` e `cge_midia`, montados em `/app/arquivos` e `/app/media`. O backup desses volumes é uma cópia do volume Docker para um diretório fora do Git, feita com o container parado ou com a escrita suspensa. A restauração devolve a cópia ao mesmo volume. O banco guarda o caminho e o hash; o arquivo sem o registro, ou o registro sem o arquivo, fica inconsistente. Restaurar os dois juntos.

## Configuração e versão

Guardar fora do Git: a imagem `cge_aplicacao:onda10-rc1`, o commit correspondente e uma cópia do `.env` do servidor em cofre separado. Não colocar essa cópia no repositório.

## Antes do primeiro processo real

Ter um dump do PostgreSQL e uma cópia dos volumes de documentos feitos depois do deploy e antes da carga. Sem esse par, a homologação não está pronta para dado real.
