# Piloto real

O primeiro processo da CGE/SC não entra com o deploy. Há dois portões.

## Checkpoint 10.1 — pré-deploy

Ambiente de notebook validado, release descrita, imagem nomeada e plano de Linux escrito. Parar e esperar autorização para implantar.

## Checkpoint 10.2 — pronto para dado real

Só depois do deploy autorizado, e só quando estiver comprovado:

- aplicação no ar;
- rede de acesso definida, com HTTPS se houver certificado, ou HTTP restrito à rede autorizada se não houver;
- login e perfis conferidos;
- banco e documentos em volume persistente;
- backup e restore documentados e um backup real já gerado;
- logs sem segredo;
- segredos só no `.env` do servidor;
- saúde e migrations conferidas;
- suíte e smoke do ambiente;
- rollback conhecido;
- `DEMO-2024-001` visível como demonstração, nunca como processo da CGE.

Sem isso, não carregar documento real.

## DEMO-2024-001

Não apagar. É o cenário de regressão. No piloto, a opção adotada até nova decisão é mantê-lo identificado como demonstração e separável pelo filtro “Somente operacionais”. Não misturar a contagem dele com processo real sem esse filtro explícito. Não movê-lo para outro banco nesta onda.

## Quando a carga for autorizada

1. Identificar o processo e gravar os metadados reais.
2. Receber os documentos no volume `cge_arquivos`, não na imagem e não no Git.
3. Classificar, extrair, aplicar normas e regras já existentes.
4. Gerar evidências e achados a partir dessa execução.
5. Produzir pré-análise e submetê-la à revisão humana.
6. Ground Truth, se houver, nasce depois e fora do prompt, do RAG, do motor, da evidência, do achado e da pré-análise. Não serve para ensinar a análise daquele mesmo processo.

Fonte excluída de teste cego continua fora do RAG, da evidência, do achado, da pré-análise e do contexto do modelo. O deploy não altera essa exclusão.

## Área de recepção — ainda sem arquivos

Nenhum documento real entra neste checkpoint. A pasta abaixo só existe no servidor, fora do Git:

`/max/entrada_piloto_cge`

Permissão `750`, dono `root`. Ela é a área de espera. O armazenamento da aplicação continua no volume `cge_arquivos`, montado em `/app/arquivos` nos serviços web e worker, e no volume `cge_midia` em `/app/media`. Esses volumes não entram na imagem nem no repositório.

Quando a carga for autorizada, o operador é um usuário já permitido a incluir documento: analista, auditor ou administrador. Consulta não envia arquivo. O processo novo nasce com a marca operacional, separado de `DEMO-2024-001` pelo filtro “Somente operacionais”. Antes de copiar qualquer arquivo, gera-se um backup novo do PostgreSQL e dos dois volumes. O rollback dessa carga futura restaura esse par e não usa `docker compose down -v`.

## PDF da pré-análise

Desejável para o piloto e dispensável para a homologação técnica. A saída oficial hoje é HTML. Um PDF novo mexe em exportação e em dependência de renderização. Fica para decisão posterior, sem implementação nesta onda.
