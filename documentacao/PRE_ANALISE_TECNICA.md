# Pré-análise técnica assistida por IA

A Onda 7 transforma achados, evidências, regras, cálculos e normas já apurados em um documento técnico versionado. A IA redige. O auditor revisa e decide. A pré-análise não é parecer e não encerra a prestação.

## Arquitetura

O app `pareceres` consome as ondas anteriores. Python e o motor continuam calculando e verificando. O resolvedor normativo continua escolhendo a norma. O agente só organiza texto a partir do contexto estruturado e passa por `GerenciadorInteligenciaArtificial`. Nenhum provedor é chamado diretamente.

Com `IA_INTEGRACAO=desligada`, a geração é determinística e não chama modelo. A suíte usa o provedor simulado quando precisa exercitar o agente.

## Modelos

- `PreAnaliseTecnica`: prestação, execução, versão, status, resumo, escopo, limitações, encaminhamento, modelo, prompt, solicitante, revisão, congelamento e hash.
- `SecaoPreAnalise`: identificação, escopo, documentação, normas, verificações, achados, limitações, avaliação humana, síntese e encaminhamento.
- `AfirmacaoPreAnalise`: texto original da IA separado do texto atual, status de validação e flag de exibição oficial.
- `FonteAfirmacaoPreAnalise`: vínculos explícitos para evidência, achado, regra, execução, norma, trecho, documento, cálculo e revisão de achado.
- `RevisaoPreAnalise`: ação humana, textos anterior e posterior, usuário e horário. Não é Ground Truth.

## Fluxo

1. O usuário autorizado solicita a geração.
2. A tarefa `pareceres.gerar_pre_analise` marca a versão como gerando.
3. O contexto é montado só com objetos da prestação, sem PDF integral, sem teste cego e sem Ground Truth.
4. As seções factuais nascem dos dados.
5. Se um gerenciador é informado, a redação segue esta cadeia:

LLM → validação estrutural → validação de completude → validação de proveniência → guardrails → Pré-Análise → revisão humana → congelamento.

6. JSON quebrado fica em `schema_invalido`. JSON válido porém vazio ou sem resumo, seção, afirmação, encaminhamento permitido ou limitações exigidas pelo contexto fica em `resposta_incompleta`. Fonte inventada ou valor não comprovado chega à proveniência e é rejeitado. Conclusão administrativa vedada não entra na versão oficial.
7. `schema_invalido` e `resposta_incompleta` autorizam no máximo uma nova tentativa, só com o erro estrutural. As duas tentativas ficam em `UsoInteligenciaArtificial`. O retry não altera o contexto factual e não recebe Ground Truth nem fonte de teste cego.
8. Uma resposta vazia não é sucesso. Afirmação não suportada ou rejeitada fica gravada e fora da versão oficial.
9. O status vai para aguardando revisão. Falha controlada vai para erro. O auditor revisa. Auditor ou administrador congela. O hash cobre a versão congelada.

## Papel do LLM

Pode organizar, sintetizar e redigir o que já está no contexto, e só pode escolher um encaminhamento do enum. Não cria fato, valor, documento, pessoa, evidência, achado, regra ou norma. Não confirma achado potencial e não declara a prestação aprovada, reprovada, regular ou irregular.

Texto de documento, OCR, evidência e norma entra como dado, não como instrução.

## Proveniência e validação

Afirmação oficial aponta para fonte existente. A interface abre o achado e, quando há documento e página, o visualizador da Onda 2. Achado inexistente, evidência inexistente, regra inexistente, norma inexistente ou fora de vigência, fonte de outra prestação, valor divergente e página inventada são rejeitados.

Evidência que suporta e evidência que contradiz aparecem juntas. Resultado não verificável não vira irregularidade. Constatação positiva só entra com suporte real. A seção de limitações sai dos dados.

## Revisão, versão, congelamento e hash

Ações: aceitar, ajustar, rejeitar e solicitar nova geração pela criação de outra versão. O texto original da IA não é sobrescrito. `versao_registro` impede gravar por cima de alteração concorrente.

A primeira geração é a versão 1. Nova geração cria a seguinte e preserva a anterior. Auditor e administrador congelam. A versão congelada não é editada. O hash SHA-256 cobre o conteúdo oficial canônico e permanece estável enquanto a versão estiver congelada.

## Ground Truth e teste cego

Ground Truth continua bloqueado: não entra no contexto, no prompt, na redação nem na revisão. Revisão da pré-análise e revisão do achado são decisões operacionais, não gabarito.

Documento `FONTE_EXCLUIDA_TESTE_CEGO` não entra na documentação, na evidência nem no achado que só se apoie nele.

## Multi-LLM e FinOps

O uso real passa por `UsoInteligenciaArtificial`: prestação, análise, agente, provedor, modelo, prompt, tokens, latência e custo. Sem preço vigente, o custo fica nulo. O painel FinOps não faz parte desta onda.

`python manage.py testar_pre_analise_ia --habilitar` é manual, só aceita prestação sintética e não é chamado pela suíte.

O smoke test de laboratório envia o mesmo contexto sintético, no cenário de demonstração, aos provedores configurados no ambiente. Ele passa pelo gerenciador, pelo agente, pelo schema, pela completude e pela proveniência. Não cria versão oficial, não usa insumo real e não grava chave nem cadeia de raciocínio. Os usos ficam marcados como laboratório no banco local e não entram no Git.

## Permissões

Consulta visualiza. Analista gera e revisa. Auditor e administrador também congelam. A autorização é verificada no backend.

## Limitações e riscos

A exportação desta onda é HTML. PDF fica pendente. A redação determinística não substitui a revisão do auditor. A validação rejeita número e código ausentes do contexto, mas uma frase genérica sem número novo pode ser aceita como contexto. A decisão administrativa continua fora do sistema.

Melhoria futura, fora deste fechamento: a proveniência ainda rejeita afirmação quando o modelo cita o número do processo de forma fragmentada ou escreve valor monetário com separador de milhar diferente do catálogo. O controle não foi afrouxado.
