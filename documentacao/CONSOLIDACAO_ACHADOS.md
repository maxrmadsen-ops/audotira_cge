# Consolidação

`GeradorAchados` lê uma `ExecucaoAnalise`, cria sinalizações só para resultados que a própria regra trata como divergência, atenção material (`POSSÍVEL…`) ou constatação positiva (`DEVOLVIDO`). Conforme, não verificável, não localizado e análise semântica pendente não viram achado negativo.

`ConsolidadorAchados` agrupa pela prestação, pelo tipo de constatação, pela natureza e pela âncora principal já gravada. A ordem é despesa, documento fiscal, pagamento, fornecedor, pessoa, item do plano e meta. Um pagamento citado só em uma das regras não separa o achado quando as duas apontam a mesma despesa. Sem âncora comum, a semelhança do texto não junta os candidatos. A chave é o SHA-256 desse núcleo. Rodar de novo a mesma análise reutiliza achado e evidências.

O agente de consolidação existe, mas o motor não o chama enquanto `IA_INTEGRACAO` estiver desligada. Se for usado, passa pelo `GerenciadorInteligenciaArtificial`, registra `UsoInteligenciaArtificial` e só guarda sugestão. Fonte ou valor ausentes do contexto tornam a sugestão inconclusiva. Ele não confirma achado, não escolhe norma e não promove criticidade crítica.

A Onda 7 consumirá estes achados na pré-análise. Esta onda não a inicia.
