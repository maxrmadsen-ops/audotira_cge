# Observabilidade

A Onda 9 observa o que as ondas anteriores já gravam. Não cria telemetria paralela e não registra a abertura de cada gráfico.

## Operação da IA

A aba Operação & IA, em `/painel/operacao/`, consolida modelos, modelos ativos, prompts, versões de prompt, execuções, sucessos, erros controlados, limite excedido, tokens e latência média em milissegundos. Os gráficos separam provedor, agente, status e erro normalizado.

Prompt, chave, autorização e corpo da resposta ficam de fora. O link de uma linha aponta para o consumo administrativo; quem não administra recebe a recusa já existente dessa tela.

O menu Inteligência Artificial abre `/ia/`, uma visão geral sem executar modelo. Laboratório, catálogo, consumo, provedores e roteamento conservam as URLs e a restrição ao administrador.

## Administração

`/administracao/` continua exclusiva do administrador. Mostra usuários, ativos, quantidade por perfil e os doze eventos mais recentes da trilha (evento, usuário e horário). Não mostra senha, segredo nem detalhe livre do evento. Não produz estatística de comportamento.

A permissão de administrador não congela Ground Truth nem avaliação.

## Saúde

`/saude/` continua exclusiva do administrador. Ao abrir, verifica localmente:

- aplicação Django;
- PostgreSQL e a extensão pgvector;
- Redis;
- Celery Worker, por ping interno;
- Celery Beat, como “Não verificado”, porque a tela não sonda o agendador;
- armazenamento, com um arquivo temporário no volume;
- fila Celery, pelo tamanho da lista `celery` no Redis;
- OpenAI e Anthropic, pelo ambiente e pelo último erro operacional já gravado.

Provedor sem chave ou desabilitado permanece “Não configurado”. A abertura da saúde não chama OpenAI nem Anthropic.

A sonda `/saude/viva/` responde apenas que a aplicação está operacional e não executa essas verificações.
