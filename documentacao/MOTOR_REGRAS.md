# Motor de regras

Onda 4. A fonte funcional é `Matriz_Tecnica_Regras_Analise_IA_2022TR929.xlsx`. O texto original está em `aplicacao/regras/dados/matriz_regras_cge.json` e no [catálogo](CATALOGO_REGRAS_CGE.md). A planilha e os documentos reais não são necessários em produção e não entram no Git.

Regra de ouro: a IA deve apontar fatos, evidências, cruzamentos e possíveis inconsistências; a conclusão cabe ao analista.

## O que o motor faz

Carrega as 89 regras ativas, respeita dependências, escolhe um executor pela configuração e grava a execução na versão da regra que rodou. Uma versão nova não altera a execução anterior.

A síntese da rodada é sempre `NÃO CONCLUSIVO`. O status final fica `Aguardando validação`. O motor não emite REGULAR, IRREGULAR, APROVADO ou REPROVADO como conclusão da prestação.

Ausência de dado produz `NÃO VERIFICÁVEL`, `NÃO LOCALIZADO` ou `INCOMPLETO`, conforme a regra. Não produz divergência.

## Executores

`ExecutorContexto`, `ExecutorDocumental`, `ExecutorComparacaoValor`, `ExecutorSomatorio`, `ExecutorComparacaoData`, `ExecutorCorrespondenciaIdentidade`, `ExecutorMovimentacaoBancaria`, `ExecutorPlanoTrabalho`, `ExecutorContrapartida`, `ExecutorDevolucao` e `ExecutorGovernanca`. Regras semânticas usam `ExecutorSemantico` e devolvem `REQUER ANÁLISE SEMÂNTICA`, sem heurística conclusiva. `VED-011` e `VED-012` ficam com o analista e não inferem parentesco pelo sobrenome. `EFE-001` e `EFE-002` permanecem `NÃO REALIZADA – ESCOPO DA V1`.

Cálculos usam `Decimal`. A correspondência de identidade exige CPF, CNPJ ou identificador equivalente nas duas pontas. Nome parecido não comprova identidade.

## Teste cego

Com `modo_teste_cego`, documentos de prestação parcial ou final marcados com `FONTE_EXCLUIDA_TESTE_CEGO`, ou cujo nome indica análise técnica prévia, saem do conjunto de entrada. A exclusão fica registrada. O texto desses documentos não alimenta resultado, evidência nem contexto semântico.

## Norma aplicável

`CTX-005` usa o `ResolvedorNormativo` da Onda 3. A data de referência escolhe a norma vigente. A fonte escrita na matriz é a indicação das diretrizes, não a versão aplicada.

## Achados

`ACH-001` e `ACH-002` só verificam se a rodada tem elementos para um achado futuro. Não existe modelo de achado nesta onda.

## Execução

`python manage.py carregar_regras_cge` sincroniza o catálogo sem duplicar. A análise completa entra na tarefa Celery `regras.executar_analise`. A falha de uma regra fica registrada e a rodada continua.

Não há chamada a OpenAI nem a Claude.
