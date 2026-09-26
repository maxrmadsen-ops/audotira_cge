# Base normativa

A base normativa é independente dos documentos da prestação de contas. Uma norma é a fonte. Um trecho normativo é um fragmento recuperável dessa fonte. Uma regra de análise, que perguntará se o dever ocorreu, fica para a Onda 4.

## O que uma norma guarda

Tipo, número, ano, título, ementa, órgão, esfera, publicação, início e fim de vigência, situação, fonte, arquivo, SHA-256, observações e a pessoa que cadastrou. Cada linha também tem grupo lógico, versão e, quando houver, a versão anterior.

Uma alteração de arquivo ou de vigência em norma já indexada cria outra versão e desativa a anterior. O hash e as datas da versão antiga permanecem.

## Vigência

A data de referência da consulta decide a norma, não a data em que a análise é feita. Uma prestação de 2018 usa a legislação vigente em 2018. Norma sem fim de vigência continua elegível. Norma com fim anterior à data de referência fica de fora.

Relacionamentos do tipo altera, revoga, substitui, regulamenta, complementa ou referencia são registros informados por uma pessoa. Esta onda não calcula efeito jurídico a partir deles.

## Aplicabilidade

Cada norma pode ter uma ou mais linhas de contexto: tipo de instrumento, órgão, tipo de prestação, período e categoria. Campo vazio não restringe aquele eixo. Sem nenhuma linha, só a vigência restringe a norma.

## Ingestão

O administrador envia um PDF. A validação, o SHA-256, a extração, o OCR seletivo, a segmentação, o chunking, o embedding e a indexação rodam na tarefa Celery `normas.processar_norma`. O texto do PDF é dado. Instruções escritas dentro do arquivo não são comandos do sistema.

## O que não entra no Git

PDFs reais da CGE, leis oficiais completas e ground truth não são versionados. Os testes usam PDFs sintéticos. O ambiente de execução pode receber, fora do Git, lei, decreto, instrução normativa, orientação técnica e manuais. O sistema não inventa o texto dessas fontes.

## Limitações

A segmentação reconhece título, capítulo, seção, artigo, parágrafo, inciso e alínea quando o texto os declara. Se a estrutura não aparece, o trecho fica sem dispositivo. Não há motor de regras, achado, evidência de análise nem modelo generativo.
