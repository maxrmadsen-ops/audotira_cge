# Preparação da análise

A preparação organiza, em cada prestação de contas, o que precisa estar conferido antes da análise. São quatro passos previstos:

1. Instrumento da Parceria — implementado neste checkpoint.
2. Base Normativa — futuro.
3. Entidade — futuro.
4. Plano de Trabalho — futuro.

Os passos 2, 3 e 4 aparecem na tela como etapas futuras e bloqueadas. Nenhuma busca de norma, cadastro de entidade ou leitura de plano é executada aqui.

## Passo 1

O analista responsável, o auditor ou o administrador:

1. abre **Preparar instrumento da parceria** na prestação;
2. seleciona um documento já vinculado ou envia o PDF;
3. dispara o processamento documental já existente (armazenamento, hash, páginas, texto, OCR quando necessário, classificação estrutural e extração determinística);
4. confere a ficha;
5. confirma, corrige com justificativa ou marca como não identificado;
6. conclui a validação de forma explícita.

OCR ou extração concluída não encerra o passo. A conclusão exige revisão humana das informações pendentes e a ação **Concluir validação do instrumento**. Campo ausente no documento pode ser marcado como não identificado. Campo ainda não revisado impede a conclusão.

Depois de validado, o termo fica congelado. Alteração posterior reabre uma nova versão e preserva a anterior. O valor extraído não é substituído pela correção.

## Proveniência

Cada campo estruturado guarda valor extraído, valor validado, página, trecho, método e situação. **Ver origem** abre a página correspondente quando ela foi determinada. Se não houver página ou trecho, a interface mostra **Origem não determinada**.

## Referências normativas

As referências citadas no instrumento são listadas como identificadas, já existentes no catálogo ou pendentes de tratamento. Não há download, consulta externa, vigência automática nem execução de regra. A ação de tratamento permanece desabilitada para o Passo 2.

## Inteligência artificial

O processamento primário é OCR, extração determinística e classificação estrutural. O prompt governado `EXTRACAO_TERMO_FOMENTO` continua versionado e não contém exemplo de processo real. Nenhuma chamada real a provedor é disparada por este passo quando a integração está desligada. Um resultado futuro de modelo, se habilitado pela governança, continua sujeito à validação humana e não decide a prestação.

## Perfis

A autorização está no servidor. Administrador e auditor atuam em qualquer prestação visível. Analista atua só na prestação em que é responsável. Analista não responsável não abre a preparação de processo alheio.

## Auditoria

Eventos registrados: instrumento selecionado, processado, classificado e reprocessado; campo confirmado, corrigido e não identificado; validação concluída e reaberta. O registro traz usuário, prestação, documento, versão e hash, sem raciocínio interno de modelo.

## Limitações

Não há integração com sistema de origem, busca na internet, análise financeira, execução das regras CGE nem parecer. A interface informa que, no piloto, o envio e a validação são manuais.
