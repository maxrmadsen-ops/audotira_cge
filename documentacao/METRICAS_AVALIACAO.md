# Métricas da avaliação

Verdadeiro positivo: a referência e a análise se correspondem por sinais estruturados, não por igualdade de texto.

Falso positivo: a análise aponta e a referência não.

Falso negativo: a referência aponta e a análise não. Fica em visão própria, com criticidade e materialidade. Não se esconde na taxa agregada.

Correspondência parcial permanece separada e não vira verdadeiro positivo. Pendência de revisão também não entra como acerto.

Precisão = TP / (TP + FP). Recall = TP / (TP + FN). F1 = 2 × precisão × recall / (precisão + recall). Denominador zero produz valor nulo, nunca zero inventado. Os cálculos usam `Decimal`.

Não se cria verdadeiro negativo para o universo aberto de achados.

A concordância das regras é o quociente entre regras concordantes e regras avaliáveis com Ground Truth válido. Ficam de fora do denominador as regras sem Ground Truth, as não aplicáveis e as fora de escopo. Não aplicável, não verificável e não localizado não são a mesma categoria. A concordância também se abre pela categoria e pelo tipo de execução já existentes no catálogo.

A materialidade dos falsos negativos soma somente valores informados. A ausência não vira R$ 0,00. A média só existe quando há ao menos um valor. A criticidade não é convertida em nota.

A proveniência reaproveita o status da pré-análise: taxa de afirmações suportadas e taxa de rejeição sobre as afirmações materiais. O motivo só entra no agrupamento quando já estava registrado.

A pré-análise congelada é lida de forma objetiva: achados presentes e omitidos, limitações, contraditórios, conclusão administrativa vedada e encaminhamento. Não há nota de qualidade do texto nem juiz por outro modelo.

Recall alto não garante ausência de risco. Um único falso negativo crítico pode ser mais relevante do que vários acertos.
