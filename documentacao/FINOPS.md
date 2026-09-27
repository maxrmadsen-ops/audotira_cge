# FinOps

O FinOps é menu próprio, em `/finops/`. Não é aba do Painel.

Ele lê `UsoInteligenciaArtificial` e `PrecoModeloInteligenciaArtificial`. O custo é calculado na leitura, com o preço cuja vigência cobre a data da chamada. Um preço cadastrado depois vale para a chamada daquela data. Um preço posterior não reescreve vigência anterior.

A fórmula segue a estimativa já existente da camada de IA: tokens divididos pela unidade de precificação (`1000000` ou `1000`), multiplicados pelo preço de entrada ou de saída, com seis casas decimais. Unidade zero, modelo ausente ou preço que não cobre a data devolvem ausência. A ausência aparece como “Não disponível”. Não vira zero.

Não há preço no código, nem consulta de preço na internet.

## O que a tela mostra

- chamadas, tokens de entrada, tokens de saída e tokens totais;
- custo total e custo por provedor, modelo, agente e prestação;
- quantidade de chamadas sem preço vigente, separada do custo;
- modelos cadastrados;
- limites ativos (`LimiteConsumoInteligenciaArtificial`: escopo, provedor, máximo de tentativas e máximo de caracteres);
- chamadas com status `limite_excedido`;
- histórico de chamadas por mês, só com dois meses distintos ou mais.

O limite cadastrado não é orçamento em reais nem cota de tokens. A tela não calcula percentual de uma cota inexistente.

Chamada com erro continua no consumo quando há registro de uso. Chamada com tokens zerados conta como sem telemetria: o campo de token não aceita nulo, e zero significa telemetria não gravada. Sem nenhuma chamada, tokens e custo ficam “Não disponível”.

## Custo e qualidade

Quando uma avaliação com métricas preenchidas compartilha a prestação de uma chamada, a tela informa a quantidade. Isso não afirma que o custo causou a precisão, o recall ou o F1. Sem essa coincidência, a tela diz que custo e qualidade não foram relacionados.

## O que não aparece

Chave, autorização, senha, prompt, cadeia de raciocínio e resposta estruturada não entram nesta tela.

Preços comerciais reais dos provedores continuam fora do repositório. Sem preço vigente, o custo permanece não disponível.
