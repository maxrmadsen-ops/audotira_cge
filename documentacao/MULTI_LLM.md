# Multi-LLM

O roteamento é um registro administrativo: provedor e modelo principais, provedor e modelo de fallback. A preferência não está fixa no código.

O fallback ocorre para timeout, indisponibilidade, limite de taxa, erro transitório, ausência de configuração do provedor principal e schema inválido depois das tentativas. Não há fallback porque a resposta pareceu fraca.

As duas tentativas geram uso, com provedor original, erro, provedor final e custos separados.

A execução oficial usa um provedor por vez. A execução dupla fica no Laboratório de IA, que grava usos com a marca de laboratório e não altera `ExecucaoRegra`.

Reexecutar uma regra semântica acrescenta tentativa e guarda o bloco anterior em `historico_ia`. Só o administrador escolhe outro modelo nessa reexecução, e essa escolha também usa o provedor simulado nesta onda para não disparar custo por engano. A chamada real continua restrita ao comando opcional.
