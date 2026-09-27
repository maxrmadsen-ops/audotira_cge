# Agentes

`AgenteBase` valida a entrada já preparada, escolhe o prompt ativo, chama o gerenciador, recebe a saída estruturada e devolve o resultado ao motor.

| Agente | Regras |
| --- | --- |
| Compatibilidade com o plano | PT-002 |
| Vedações | VED-001 a VED-008 |
| Princípios | PRI-001 a PRI-007 |
| Objeto e metas | OBJ-001 a OBJ-003 |
| Análise semântica | Demais regras `requer_ia`, como DES-002, DES-005, CLA-001 e CLA-004 |
| Pré-análise técnica | Só consolida fatos já produzidos. Não emite parecer nem o documento da Onda 7 |

A saída pede resultado, justificativa, fatos, fontes, fundamentos, limitações, dados insuficientes e revisão humana. `REGULAR`, `IRREGULAR`, `APROVADO` e `REPROVADO` são rejeitados.

Não há indicador de autoconfiança do modelo. Ele não seria uma probabilidade estatística.

O prompt de sistema declara que documento e norma são dados. Um pedido dentro do PDF para aprovar a prestação não é comando.

Fonte citada que não estava no contexto é rejeitada e não vira evidência. O resultado dessa chamada fica inconclusivo.
