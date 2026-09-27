# Inteligência artificial

O motor de regras continua dono da execução. Uma regra com capacidade `requer_ia` só chama um agente quando `IA_INTEGRACAO` está `simulada` ou `configurada`. O padrão é `desligada`, e a suíte força esse padrão para não gastar tokens.

Fluxo: motor, preparação do contexto, agente, gerenciador, provedor, validação de schema, validação de fontes, retorno ao motor, pendência de validação humana.

## Provedores

OpenAI e Anthropic existem como adaptadores HTTP em `provedores/`. Nenhuma regra, view de negócio ou agente importa o contrato desses provedores. O provedor simulado cobre a suíte e o laboratório.

A saúde mostra Configurado, Não configurado ou Indisponível. Indisponível usa o último erro operacional já gravado. A tela não faz chamada.

## O que fica armazenado

`UsoInteligenciaArtificial` guarda provedor, modelo, agente, regra, análise, prestação, tempos, tokens, custo estimado, status, erro normalizado, id da requisição e a resposta estruturada.

Não armazenamos chave, cabeçalho de autorização, raciocínio interno nem o PDF. O prompt versionado fica na tabela de versões, sem dados da prestação. A retenção automática não está nesta onda: o registro existe para auditoria e para o FinOps da Onda 9.

## Custo

`PrecoModeloInteligenciaArtificial` é administrável, com vigência. Sem preço vigente, o uso grava tokens e deixa o custo vazio. Nenhum preço comercial está no código.

## Limites

Há limite de caracteres de contexto e de tentativas. Contexto acima do limite não gera chamada.

## Comando real

`python manage.py testar_provedores_ia` só corre com `IA_INTEGRACAO=configurada` e não faz parte da suíte.
