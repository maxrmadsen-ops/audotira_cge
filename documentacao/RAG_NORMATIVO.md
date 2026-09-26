# RAG normativo

A recuperação não escolhe a legislação pela similaridade. O fluxo é fixo:

```text
consulta e contexto
        ↓
data de referência, instrumento, órgão e categoria
        ↓
ResolvedorNormativo
        ↓
normas elegíveis
        ↓
busca lexical e busca vetorial, só nessas normas
        ↓
ranking híbrido
        ↓
trechos com norma, dispositivo, página, vigência e scores
        ↓
ConsultaNormativa gravada
```

## Resolução

`ResolvedorNormativo` lê vigência e aplicabilidade. Uma norma entra quando está ativa, processada, com início de vigência informado, a data de referência cai no intervalo e ao menos uma linha de aplicabilidade cobre o contexto. A justificativa fica no resultado da consulta, inclusive para as normas descartadas.

## Chunking

Artigo pequeno permanece inteiro. Artigo maior que `NORMATIVO_CHUNK_MAXIMO` é dividido com sobreposição `NORMATIVO_CHUNK_SOBREPOSICAO`, conservando artigo, parágrafo, inciso e alínea já identificados. Texto sem estrutura usa janela com a mesma sobreposição.

## Embeddings

`GerenciadorEmbeddings` escolhe o provedor por `EMBEDDING_PROVEDOR`. Nesta onda o provedor entregue é `simulado`: vetor determinístico de `EMBEDDING_DIMENSAO` posições, modelo `EMBEDDING_MODELO`, sem rede. A coluna `embedding` usa pgvector, com índice HNSW de cosseno. Trocar a dimensão exige nova migração. Embedding não é chamada de modelo generativo.

## Busca

A busca lexical usa o texto normalizado e a configuração `portuguese` do PostgreSQL. A busca vetorial calcula distância de cosseno somente nos identificadores elegíveis. O score final é `NORMATIVO_PESO_LEXICAL` vezes o score lexical normalizado mais `NORMATIVO_PESO_VETORIAL` vezes a similaridade. O método registrado é lexical, vetorial ou híbrido.

## Rastreabilidade

`ConsultaNormativa` guarda texto, data de referência, filtros, normas consideradas e motivo. `ResultadoConsultaNormativa` guarda o trecho, os três scores e o método. A trilha de auditoria registra a consulta sem o arquivo e sem segredo. A tela Pesquisa normativa mostra consideradas, descartadas, dispositivo, página, vigência, scores e link da fonte. Ela não aprova prestação.

## Limitações

Não há chat, agente, OpenAI nem Anthropic nesta onda. A busca não percorre normas fora de vigência, mesmo que o texto seja idêntico ao da consulta. O painel mostra contagens reais da base; indicadores de análise continuam aguardando as ondas seguintes.
