# Achados

Um achado automático nasce `potencial`. Confirmação, descarte, ajuste e diligência exigem usuário autorizado e ficam em `RevisaoAchado`. A saída original não é apagada.

A descrição factual, a interpretação e a possível implicação ficam separadas. O texto automático não acusa fraude, crime ou má-fé, salvo citação literal de fonte permitida.

Materialidade financeira é `Decimal` e pode ser nula. Criticidade e prioridade são escalas distintas. A geração determinística não atribui criticidade crítica. Não há score numérico nesta onda: a prioridade operacional basta e é reproduzível a partir da criticidade e da materialidade.

Constatação positiva, como devolução identificada, não se mistura com achado potencial negativo. Evidência insuficiente permanece sinalizada e não pode ser confirmada enquanto a lacuna existir.

ACH-001 e ACH-002 continuam com os textos da matriz. Depois que os objetos existem, a rastreabilidade e a fundamentação são avaliadas neles. A execução histórica da regra não é reescrita. ACH-001 atende somente com fato, regra, evidência e rastreabilidade. ACH-002 atende somente com norma e trecho normativo reais e vigentes. Norma fora da vigência não atende.

`RevisaoAchado` registra a decisão operacional humana sobre o achado. Essa revisão não constitui automaticamente Ground Truth. O Ground Truth continua isolado e será tratado na Onda 8.

Tempo médio de revisão, score numérico e novas métricas não foram implementados nesta onda. Permanecem pendências futuras.
