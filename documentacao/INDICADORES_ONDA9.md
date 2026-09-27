# Indicadores da Onda 9

Todo número do Painel e do FinOps sai das consultas em `aplicacao/painel/consultas/`. O template não agrega.

## Contrato comum

| Campo | Regra |
|---|---|
| Objetivo | Mostrar o que já está gravado, sem concluir a prestação e sem inventar classificação. |
| Filtros | Só dimensões existentes. A Visão 360° filtra prestações e inclui os filhos dessas prestações. As outras abas filtram o próprio objeto. Origem `demonstracao` ou `operacional` usa a marca já gravada. |
| Período | `criado_em`, salvo evidência (`criada_em`), uso de IA (`iniciada_em`) e revisão (`data_hora`). |
| NULL | Permanece “Não disponível”. Não vira zero. |
| Zero | Contagem real de um conjunto vazio de ocorrências. No gráfico, balde zero não desenha barra; o card conserva o zero. |
| Denominador zero | Precisão, recall, F1 e taxa de concordância ficam “Não disponível”. Não aparece 0%. |
| Histórico | Uma série só entra com dois meses distintos ou mais. Mês sem evento não é preenchido com zero. Caso contrário: “Sem dados históricos suficientes.” |
| Perfil | Administrador, auditor, analista e consulta leem. O destino do drill-down aplica a permissão da tela operacional. |
| Auditoria | Ler o indicador não gera evento. |

A materialidade é `Decimal`. A soma ignora nulos. Se todos os valores são nulos, a soma é “Não disponível” e a contagem “sem materialidade” permanece separada.

## Visão 360°

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Prestações cadastradas | Prestações do recorte | Contagem | — | `PrestacaoContas` | Aba Processos | |
| Em análise | Situação `em_analise` | Contagem | — | `PrestacaoContas.situacao` | Processos com a situação | Não é SLA |
| Concluídas | Situação `concluida` | Contagem | — | `PrestacaoContas.situacao` | Processos com a situação | |
| Com achados | Prestação com ao menos um achado | Contagem distinta | — | `Achado` | Aba Achados | |
| Achados críticos | Criticidade alta ou crítica | Contagem | — | `Achado.criticidade` | Achados com `alta_ou_critica` | Não cria criticidade |
| Materialidade dos achados | Soma das materialidades informadas | Soma | — | `Achado.materialidade_financeira` | Aba Achados | Nulos fora da soma |
| Documentos | Documentos não excluídos das prestações do recorte | Contagem | — | `Documento` | Aba Documentos | |
| Regras executadas | Execuções de regra dessas prestações | Contagem | — | `ExecucaoRegra` | Aba Regras | Não é o catálogo |
| Evidências | Evidências dessas prestações | Contagem | — | `Evidencia` | Aba Evidências | |
| Achados | Achados dessas prestações | Contagem | — | `Achado` | Aba Achados | |
| Pré-análises | Versões dessas prestações | Contagem | — | `PreAnaliseTecnica` | Aba Pré-Análise | Não é parecer conclusivo |
| Revisões humanas | Revisões de achado, pré-análise e correspondência | Soma das três contagens | — | `RevisaoAchado`, `RevisaoPreAnalise`, `RevisaoCorrespondencia` | Aba Revisão Humana | |
| Processos por etapa | Prestações por situação | Contagem por situação | — | `PrestacaoContas.situacao` | Processos filtrados | |
| Achados por criticidade | Achados por criticidade cadastrada | Contagem por valor | — | `Achado.criticidade` | Achados filtrados | |
| Achados por natureza | Achados por natureza cadastrada | Contagem por valor | — | `Achado.natureza` | Achados filtrados | |
| Evolução das análises | Meses distintos de prestações, documentos, execuções, evidências, achados e pré-análises | Contagem no mês | — | Datas de criação | — | Série com um mês não entra |

## Processos

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Prestações | Carteira filtrada | Contagem | — | `PrestacaoContas` | Linha abre a prestação | |
| Em análise | Situação `em_analise` | Contagem | — | `situacao` | — | |
| Concluídas | Situação `concluida` | Contagem | — | `situacao` | — | |
| Com achados | Prestação com achado | Contagem | — | `Achado` | — | |
| Sem achados | Prestação sem achado | Contagem | — | `Achado` | — | Zero é ausência de achado, não de dado |
| Prestações por situação | Agrupamento da situação | Contagem | — | `situacao` | — | Não é SLA |
| Prestações por fase | Agrupamento da fase | Contagem | — | `fase` | — | |
| Por tipo de instrumento principal | Instrumento marcado como principal | Contagem distinta | — | `Instrumento.tipo` | — | Sem principal: estado vazio |

## Documentos

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Recebidos | Documentos ativos do recorte | Contagem | — | `Documento` | Linha abre o documento | Exclui `excluido_em` |
| Processados | Status processado | Contagem | — | `status_processamento` | — | |
| Aguardando validação | Status correspondente | Contagem | — | `status_processamento` | — | |
| Com erro | Status erro | Contagem | — | `status_processamento` | — | |
| Páginas | Soma de `quantidade_paginas` | Soma | — | `Documento.quantidade_paginas` | — | Tudo nulo: não disponível |
| Usados como evidência | Documento com evidência | Contagem distinta | — | `Evidencia.documento` | — | |
| Ainda não usados como evidência | Documento sem evidência | Contagem | — | `Evidencia.documento` | — | |
| Excluídos do teste cego | Subtipo da fonte excluída | Contagem | — | `subtipo_documento` | — | Não é evidência válida da análise cega |
| Documentos por tipo | Agrupamento do tipo | Contagem | — | `tipo_documento` | — | |
| Método de extração | Páginas por método | Contagem | — | `PaginaDocumento.metodo_extracao` | — | Documento sem página não entra |
| Status de processamento | Agrupamento do status | Contagem | — | `status_processamento` | — | |
| Qualidade da extração | Páginas por qualidade | Contagem | — | `PaginaDocumento.qualidade_extracao` | — | |

## Normas e referenciais

A vigência continua a da Onda 3. Norma fora de vigência não é fundamentação válida.

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Normas cadastradas | Normas do recorte de data e situação | Contagem | — | `Norma` | Lista e detalhe da norma | Norma não tem marca de demonstração |
| Vigentes | Situação vigente | Contagem | — | `Norma.situacao` | — | |
| Não vigentes | Demais situações | Contagem | — | `Norma.situacao` | — | Não fundamentam |
| Processadas | Processamento disponível | Contagem | — | `status_processamento` | — | |
| Com erro | Processamento com erro | Contagem | — | `status_processamento` | — | |
| Trechos indexados | Trechos das normas do recorte | Contagem | — | `TrechoNormativo` | — | |
| Aplicabilidades | Aplicabilidades dessas normas | Contagem | — | `AplicabilidadeNorma` | — | |
| Consultas normativas | Todas as consultas gravadas | Contagem | — | `ConsultaNormativa` | — | Não pertencem a uma prestação |
| Usadas em fundamentação vigente | Normas vigentes citadas | Normas distintas | — | `FundamentacaoAchado` | — | |
| Citações de norma não vigente | Normas não vigentes citadas | Normas distintas | — | `FundamentacaoAchado` | — | Rastreio, não fundamento válido |
| Normas por situação | Agrupamento da situação | Contagem | — | `Norma.situacao` | — | |
| Normas por aplicabilidade | Tipo de instrumento da aplicabilidade | Contagem | — | `AplicabilidadeNorma.tipo_instrumento` | — | Vazio significa sem restrição |

## Regras e verificações

O texto das 89 regras não muda. “Cadastradas” conta o catálogo dentro do recorte de regra, categoria e tipo, não um número fixo.

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Regras cadastradas | Regras do recorte de catálogo | Contagem | — | `RegraAnalise` | Lista e detalhe | |
| Executadas no recorte | Regras distintas com execução filtrada | Conjunto de `regra_id` | — | `ExecucaoRegra` | Linha da regra | |
| Não executadas no recorte | Catálogo menos as executadas | Contagem | — | `RegraAnalise` | — | |
| Automáticas | Capacidade automática | Contagem | — | `capacidade` | — | |
| Parciais | Capacidade parcial | Contagem | — | `capacidade` | — | |
| Requer IA | Capacidade correspondente | Contagem | — | `capacidade` | — | |
| Requer analista | Capacidade correspondente | Contagem | — | `capacidade` | — | |
| Fora do escopo | Tipo fora do escopo da V1 | Contagem | — | `tipo_execucao` | — | |
| Conformes | Resultado funcional igual a CONFORME | Contagem | — | `resultado_funcional` | — | Igualdade textual |
| Divergentes | Igual a DIVERGÊNCIA | Contagem | — | `resultado_funcional` | — | |
| Não verificáveis | Igual a NÃO VERIFICÁVEL | Contagem | — | `resultado_funcional` | Regra da execução | Não se confunde com não aplicável |
| Não localizadas | Igual a NÃO LOCALIZADO | Contagem | — | `resultado_funcional` | Regra da execução | |
| Com erro técnico | `status_tecnico` erro | Contagem | — | `ExecucaoRegra` | — | |
| Regras por categoria | Agrupamento da categoria | Contagem | — | `RegraAnalise.categoria` | Lista de regras | |
| Regras por tipo de execução | Agrupamento do tipo | Contagem | — | `tipo_execucao` | — | |
| Resultados das verificações | Conforme, divergência, não verificável, não localizado, não aplicável e outros | Contagem de cada texto | — | `resultado_funcional` | — | Os textos não são fundidos |
| Automação das regras | Agrupamento da capacidade | Contagem | — | `capacidade` | — | |

## Evidências

Órfã é ausência de documento, de execução de regra e de vínculo com achado. Não significa evidência inválida.

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Evidências | Evidências do recorte | Contagem | — | `Evidencia` | Documento ou prestação | |
| Suportam | Vínculos com papel suporta | Contagem de vínculos | — | `AchadoEvidencia.papel` | — | |
| Contradizem | Papel contradiz | Contagem de vínculos | — | `AchadoEvidencia.papel` | — | |
| Contextualizam | Papel contextualiza | Contagem de vínculos | — | `AchadoEvidencia.papel` | — | Não há categoria “neutra” separada |
| Validadas | Status validada | Contagem | — | `status_validacao` | — | |
| Aguardando revisão | Status pendente | Contagem | — | `status_validacao` | — | |
| Órfãs | Sem documento, regra e achado | Contagem | — | Relacionamentos | Prestação | Não invalida |
| Vinculadas a regra | Com execução de regra | Contagem | — | `execucao_regra` | — | |
| Vinculadas a achado | Com vínculo | Contagem distinta | — | `AchadoEvidencia` | — | |
| Evidências por papel | Agrupamento do papel | Contagem | — | `papel` | — | Sem vínculo não entra |
| Evidências por tipo | Agrupamento do tipo | Contagem | — | `Evidencia.tipo` | — | |

## Achados

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Achados | Achados do recorte | Contagem | — | `Achado` | Detalhe do achado | |
| Aguardando revisão | Status em revisão | Contagem | — | `status` | — | |
| Confirmados | Status confirmado | Contagem | — | `status` | — | Confirmação humana já gravada |
| Críticos | Alta ou crítica | Contagem | — | `criticidade` | — | |
| Com materialidade | Valor não nulo | Contagem | — | `materialidade_financeira` | — | |
| Sem materialidade | Valor nulo | Contagem | — | `materialidade_financeira` | — | Não entra na soma |
| Materialidade total | Soma dos valores existentes | Soma | — | `materialidade_financeira` | — | Tudo nulo: não disponível |
| Rastreáveis | `elementos_rastreaveis` verdadeiro | Contagem | — | Campo do achado | — | |
| Fundamentação insuficiente | `fundamentacao_suficiente` falso | Contagem | — | Campo do achado | — | Não cria classificação nova |
| Achados por status | Agrupamento do status | Contagem | — | `status` | — | |
| Achados por criticidade | Agrupamento da criticidade | Contagem | — | `criticidade` | — | |
| Achados por categoria | Categoria textual | Contagem | — | `categoria` | — | |
| Materialidade | Soma por criticidade | Soma | — | `materialidade_financeira` | — | Criticidade sem valor fica de fora |

A linha do achado abre o detalhe operacional, de onde seguem evidência, documento, regra, cálculo, norma, pré-análise e revisão já existentes.

## Pré-análise

A pré-análise não declara regular, irregular, aprovado ou reprovado.

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Pré-análises | Versões do recorte | Contagem | — | `PreAnaliseTecnica` | Detalhe da versão | |
| Aguardando revisão | Status correspondente | Contagem | — | `status` | — | |
| Congeladas | Status congelada | Contagem | — | `status` | — | Congelada não é decisão administrativa |
| Versões | Mesma contagem de registros | Contagem | — | `PreAnaliseTecnica` | — | Cada versão é um registro |
| Afirmações determinísticas | Origem determinística | Contagem | — | `AfirmacaoPreAnalise.origem_conteudo` | — | |
| Afirmações redigidas por IA | Origem IA | Contagem | — | `origem_conteudo` | — | |
| Afirmações alteradas por humano | Origem humana | Contagem | — | `origem_conteudo` | — | |
| Afirmações rejeitadas | Validação rejeitada | Contagem | — | `status_validacao` | — | |
| Com limitação registrada | Texto de limitação preenchido | Contagem | — | `limitacoes` | — | |
| Pré-análises por status | Agrupamento do status | Contagem | — | `status` | — | |
| Origem das afirmações | Agrupamento da origem | Contagem | — | `origem_conteudo` | — | |
| Encaminhamentos | Agrupamento do encaminhamento | Contagem | — | `encaminhamento` | — | Não aprova nem reprova |

## Revisão humana

O tempo é decorrido entre eventos. Não é tempo de trabalho e não estima economia de esforço.

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Intervenções | Revisões de achado, pré-análise e correspondência | Soma | — | Três modelos de revisão | Detalhe do objeto | |
| Usuários envolvidos | Usuários distintos dessas revisões | Contagem | — | `usuario` | — | |
| Auditores | Envolvidos com perfil auditor | Contagem | — | `Usuario.perfil` | — | |
| Analistas | Envolvidos com perfil analista | Contagem | — | `Usuario.perfil` | — | |
| Aceitações de achado | Ação confirmar | Contagem | — | `RevisaoAchado.acao` | Achado | |
| Rejeições de achado | Ação descartar | Contagem | — | `RevisaoAchado.acao` | Achado | |
| Ajustes de achado | Ação ajustar | Contagem | — | `RevisaoAchado.acao` | Achado | |
| Revisões de pré-análise | Registros do recorte | Contagem | — | `RevisaoPreAnalise` | Pré-análise | |
| Revisões de correspondência | Registros do recorte | Contagem | — | `RevisaoCorrespondencia` | Avaliação | |
| Tempo decorrido médio até a revisão do achado | Média de `data_hora` menos criação do achado, em horas | Soma das durações | Quantidade de revisões de achado | `RevisaoAchado` | — | Sem revisão: não disponível |

## IA × técnico

Usa somente correspondências e comparações da Onda 8. Parcial e pendente não entram em precisão nem em recall. Não há nota geral.

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Avaliações | Avaliações do recorte | Contagem | — | `AvaliacaoInteligenciaArtificial` | Lista e detalhe | |
| Ground Truths vinculados | Ground Truth distinto dessas avaliações | Contagem distinta | — | `GroundTruthPrestacao` | — | Não retroalimenta a análise |
| Verdadeiros positivos | Classificação correspondente | Contagem | — | `CorrespondenciaAchado` | Avaliação | |
| Falsos positivos | Classificação correspondente | Contagem | — | `CorrespondenciaAchado` | Avaliação | |
| Falsos negativos | Classificação correspondente | Contagem | — | `CorrespondenciaAchado` | Avaliação | |
| Correspondências parciais | Classificação parcial | Contagem | — | `CorrespondenciaAchado` | — | Fora de precisão e recall |
| Pendências | Pendente de revisão | Contagem | — | `CorrespondenciaAchado` | — | Fora de precisão e recall |
| Precisão | TP / (TP + FP) no recorte | TP | TP + FP | Correspondências | — | Denominador zero: não disponível |
| Recall | TP / (TP + FN) | TP | TP + FN | Correspondências | — | Denominador zero: não disponível |
| F1 | 2PR / (P + R) | — | P + R | Precisão e recall do recorte | — | Qualquer lado indisponível: não disponível |
| Falsos negativos críticos | FN cuja referência é alta ou crítica | Contagem | — | `GroundTruthAchado.criticidade` | Falso negativo | |
| Materialidade dos falsos negativos críticos | Soma das materialidades existentes desses FN | Soma | — | `GroundTruthAchado.materialidade` | — | Nulos fora da soma |
| Matriz IA × técnico | TP, FP, FN, parcial e pendente | Contagem de cada classe | — | `classificacao` | — | |
| Desempenho por categoria de regra | Concordantes / avaliáveis | Comparações concordantes | Comparações avaliáveis | `ComparacaoRegra` | — | Fora de escopo não entra |
| Desempenho por tipo de execução | Mesma taxa | Concordantes | Avaliáveis | `ComparacaoRegra` | — | |
| Precisão e recall da linha | Métrica gravada na avaliação | Valor JSON | — | `metricas` | Detalhe | JSON nulo: não disponível |

## Operação e IA

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Modelos cadastrados | Todos os modelos | Contagem | — | `ModeloInteligenciaArtificial` | — | Não filtrado pela chamada |
| Modelos ativos | `ativo` verdadeiro | Contagem | — | `ModeloInteligenciaArtificial` | — | |
| Prompts | Prompts cadastrados | Contagem | — | `PromptInteligenciaArtificial` | — | Texto não é exibido |
| Versões de prompt | Versões cadastradas | Contagem | — | `VersaoPromptInteligenciaArtificial` | — | Texto não é exibido |
| Execuções | Chamadas do recorte | Contagem | — | `UsoInteligenciaArtificial` | Consumo administrativo | Consulta recebe 403 nesse destino |
| Sucessos | Status sucesso | Contagem | — | `status` | — | |
| Erros controlados | Status erro controlado | Contagem | — | `status` | — | |
| Limite excedido | Status correspondente | Contagem | — | `status` | — | |
| Tokens de entrada | Soma gravada | Soma | — | `tokens_entrada` | — | Sem chamada: não disponível |
| Tokens de saída | Soma gravada | Soma | — | `tokens_saida` | — | |
| Tokens totais | Soma gravada | Soma | — | `tokens_total` | — | |
| Latência média (ms) | Média de `duracao_ms` | Soma | Chamadas | `duracao_ms` | — | Sem chamada: não disponível |
| Sem telemetria de tokens | Entrada, saída e total iguais a zero | Contagem | — | Tokens da chamada | — | Zero aqui é telemetria ausente |
| Execuções por provedor | Agrupamento do provedor | Contagem | — | `provedor` | — | Sem chave |
| Execuções por agente | Agrupamento do agente | Contagem | — | `agente` | — | |
| Status das chamadas | Agrupamento do status | Contagem | — | `status` | — | |
| Erros normalizados | Código de erro preenchido | Contagem | — | `erro_normalizado` | — | Sem prompt nem resposta |

## FinOps

O custo é calculado na leitura. Ver [FinOps](FINOPS.md).

| Nome | Definição | Numerador | Denominador | Origem | Drill-down | Observação |
|---|---|---|---|---|---|---|
| Chamadas | Usos do recorte | Contagem | — | `UsoInteligenciaArtificial` | — | Sem chamada: não disponível |
| Tokens de entrada | Soma | Soma | — | `tokens_entrada` | — | Sem chamada: não disponível |
| Tokens de saída | Soma | Soma | — | `tokens_saida` | — | |
| Tokens totais | Soma | Soma | — | `tokens_total` | — | |
| Custo total | Soma dos custos com preço vigente | Soma em Decimal | — | `PrecoModeloInteligenciaArtificial` na data da chamada | — | Sem preço: não disponível, não zero |
| Chamadas sem preço vigente | Chamadas cujo custo não pôde ser calculado | Contagem | — | Preço e modelo | — | Separadas do custo |
| Modelos | Modelos cadastrados | Contagem | — | `ModeloInteligenciaArtificial` | — | |
| Limites ativos | Limites com `ativo` | Contagem | — | `LimiteConsumoInteligenciaArtificial` | Tabela de limites | Não é orçamento |
| Chamadas com limite excedido | Status `limite_excedido` | Contagem | — | `status` | — | Sem percentual de cota |
| Custo por provedor, modelo, agente e prestação | Soma do custo calculado | Soma | — | Preço vigente | — | Grupo sem preço não vira zero |
| Histórico de chamadas | Chamadas por mês | Contagem | — | `iniciada_em` | — | Dois meses ou “sem dados históricos suficientes” |

## Administração e saúde

Essas telas não são indicadores analíticos da prestação.

| Nome | Definição | Origem | Observação |
|---|---|---|---|
| Usuários | Contagem | `Usuario` | Sem senha |
| Usuários ativos | `is_active` | `Usuario` | |
| Por perfil | Contagem por perfil | `Usuario.perfil` | |
| Últimas atividades | Doze eventos recentes | `RegistroAuditoria` | Sem detalhe livre |
| Componentes de saúde | Estado local de aplicação, banco, Redis, worker, armazenamento, fila e provedores | Verificações de [Observabilidade](OBSERVABILIDADE.md) | Beat fica “Não verificado”; provedor sem habilitação fica “Não configurado” |
