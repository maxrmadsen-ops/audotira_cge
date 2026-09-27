# Ground Truth

O Ground Truth é a referência técnica construída depois que a análise já foi congelada. Ele não participa da geração.

A fronteira é esta:

processo, análise, evidências, achados, pré-análise, revisão humana e congelamento da análise; só então Ground Truth, validação, congelamento do Ground Truth, comparação, revisão das correspondências, métricas e congelamento da avaliação.

É proibido enviar Ground Truth a agente de análise, ao RAG, ao prompt de geração ou ao motor de regras. Também é proibido alterar execução de regra, evidência, achado ou pré-análise a partir do Ground Truth, regenerar a análise depois de conhecê-lo, ou transformar revisão de achado ou de pré-análise em Ground Truth.

## Modo cego e modo assistido

No modo cego, a elaboração não mostra achados da solução, pré-análise, encaminhamento, correspondências nem métricas. Documentos e normas legítimos continuam visíveis. A rota de contexto da elaboração também omite esse resultado. No modo assistido, o técnico pode ver o resultado automatizado. Métricas dos dois modos não são somadas.

## Versionamento e hash

Rascunho, em validação, validado e congelado. Somente a versão validada pode ser congelada, e somente o auditor congela. A permissão de administrador não é autoridade técnica para esse ato. O congelamento grava SHA-256 do conteúdo funcional. Consultar a versão não muda o hash. Uma alteração posterior cria nova versão e preserva a anterior.

## Fundamentação

O achado de referência aponta fato, evidência, regra, norma ou trecho vigente e materialidade quando existir. Norma fora de vigência não fundamenta. Ausência de materialidade permanece nula.
