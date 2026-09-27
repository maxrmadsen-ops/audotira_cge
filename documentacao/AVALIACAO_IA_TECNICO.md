# Avaliação IA × técnico

A avaliação aponta um instantâneo da análise congelada e um Ground Truth congelado. O instantâneo guarda a prestação, a execução, a versão e o hash da pré-análise, as regras, os achados, as evidências, as normas, o prompt e o modelo registrados. Ele responde qual era o estado da análise no cálculo. Uma pré-análise posterior não reescreve o instantâneo antigo.

A tarefa `avaliacao.executar_avaliacao` compara regras e achados. Correspondência ambígua fica pendente de revisão humana. Uma sugestão semântica, quando houver, passa pelo gerenciador e não decide o caso ambíguo. A suíte usa somente simulador ou objeto falso e não chama provedor real.

A avaliação concluída pode ser congelada. O hash SHA-256 cobre correspondências, comparações e métricas. Ground Truth novo ou critério novo não recalcula a versão congelada: cria-se outra avaliação.

A tela mostra precisão, recall, F1, concordância das regras, verdadeiros positivos, falsos positivos, falsos negativos e correspondências parciais. Métrica indefinida aparece como “Não disponível”. Não há nota única da IA.

O falso negativo crítico abre o achado de referência, a regra, a evidência, o documento quando existir, a norma e a pré-análise original.

Recall alto não garante ausência de risco. Um único falso negativo crítico pode ser mais relevante do que vários acertos.
