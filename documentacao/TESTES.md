# Testes

Os testes da fundação ficam junto aos aplicativos e rodam dentro do container, contra PostgreSQL:

```bash
docker compose exec -T cge_web python manage.py test
docker compose exec -T cge_web python manage.py check
```

A Onda 10 acrescenta testes da versão `1.0.0-rc1`, do cookie Secure condicionado, da imagem sem porta de banco ou Redis, do exemplo de ambiente sem segredo, do período empilhado, da leitura de migrations na saúde e da tela de entrada, que deve mostrar a onda corrente e não o texto fixo da Onda 9. A suíte não chama OpenAI nem Anthropic. O deploy Linux não faz parte da suíte.

A Onda 9 acrescenta testes da Visão 360° com e sem dados, da diferença entre nulo e zero, da série histórica insuficiente, dos filtros combinados, das permissões, do drill-down, da central de atenção, de documentos, normas, regras, evidência órfã, achados, materialidade decimal, pré-análise, revisão humana, TP/FP/FN, precisão, recall, F1, denominador zero, falso negativo crítico, operação de IA, tokens, custo sem preço, custo com vigência, isolamento do Ground Truth, teste cego, demonstração, ausência de segredo, menu estreito, ausência de CDN e das URLs anteriores. A suíte não chama OpenAI nem Anthropic.

A Onda 8 acrescenta testes de isolamento do Ground Truth, congelamento, hash, modo cego no backend, TP, FP, FN, correspondência parcial, pendência, precisão, recall, F1, divisão por zero, regras fora do denominador, materialidade em Decimal, falso negativo crítico, norma revogada, matching estruturado, sugestão semântica não decisória, revisão humana e permissão exclusiva do auditor para congelar. A suíte não chama LLM real.

O checkpoint 7.1 acrescenta testes de resposta vazia, seção sem afirmação, afirmação material sem fonte, encaminhamento fora do enum, fonte inventada que chega à proveniência, resposta governada, retry único de schema inválido e de resposta incompleta, duas falhas seguidas, contexto factual intacto no retry, Ground Truth e teste cego ausentes do retry, e métricas separadas por tentativa. A suíte não chama LLM real.

O checkpoint da Onda 7 torna explícitos o valor divergente do cálculo, a fonte de outra prestação, o não localizado, as quatro conclusões vedadas, o Ground Truth fora do prompt e a imutabilidade da versão congelada diante da versão seguinte.

A Onda 7 acrescenta testes de geração estruturada, versionamento, proveniência, valor e página inventados, norma fora de vigência, Ground Truth, teste cego direto e indireto, evidência contraditória, limitação, constatação positiva, conclusões vedadas, preservação do texto da IA, revisão que não cria Ground Truth, congelamento, hash, concorrência, provedor simulado sem rede, custo nulo e permissão no backend. `python manage.py testar_pre_analise_ia` fica de fora da suíte.

A Onda 6 acrescenta testes explícitos de ACH-001 (sem evidência não atende; com fato, regra, evidência e rastreio atende) e de ACH-002 (sem fundamento, com norma vigente e com norma fora da vigência). Acrescenta também testes de evidência (documental, estruturada, calculada, normativa, cruzamento, semântica e humana), papéis inclusive contraditório, achado que nasce potencial, consolidação por âncora, reprocessamento, fundamentação vigente, revisão humana, teste cego e agente que não inventa fonte. A suíte continua sem chamada paga.

A Onda 5 acrescenta testes de provedor simulado, OpenAI e Anthropic mockados, fallback, schema, fonte válida e fonte inventada, prompt versionado, preço por vigência, tokens, custo, latência, idempotência, reexecução, teste cego, prompt injection, Ground Truth, minimização, retorno ao motor e laboratório sem alterar a execução oficial. A suíte não chama provedor pago. `python manage.py testar_provedores_ia` fica de fora da suíte.

A Onda 4 acrescenta testes das 89 regras, das 19 categorias, dos campos originais, da carga idempotente, da versão imutável da execução, de diferença em `Decimal`, de ausência que não vira divergência, de vigência da despesa, de identidade por CNPJ, de parentesco não inferido, de regra semântica sem conclusão, de eficácia fora da V1, do teste cego, da vigência normativa, da falha isolada, da dependência de contrapartida, da interface e da vedação de conclusão administrativa. Os testes das ondas anteriores permanecem na suíte.

A Onda 3 acrescenta testes de norma, trecho, vigência aberta e encerrada, relacionamento sem efeito automático, aplicabilidade, data histórica, segmentação, chunking, hash, embedding simulado, pgvector, busca lexical, vetorial e híbrida, filtro antes da busca vetorial, resolução, recuperação, rastreabilidade, permissões, auditoria, reprocessamento, PDF sintético, ausência de resultado e preservação de versão. Os testes das ondas anteriores permanecem na suíte.

A Onda 2 acrescenta testes de upload, MIME, tamanho, SHA-256, duplicidade, permissões, armazenamento, extração nativa, OCR, falha parcial, classificação, correção humana, metadados, Celery, reprocessamento, auditoria e visualização protegida. Os testes das ondas anteriores permanecem na suíte.

A Onda 1 acrescenta testes de entidades, prestação, instrumento, plano, itens, parciais, despesa, documento fiscal, pagamento, movimentação, meta, contrapartida, devolução, `Decimal`, ordenação, permissões, dados incompletos, linha do tempo, auditoria e cenário sintético. Os testes da Onda 0 permanecem na suíte.

Cobertura da fundação:

- perfis e permissões de execução, validação e administração
- login, falha de login e trilha sem senha
- bloqueio de administração e saúde para o perfil Consulta
- painel sem dados fictícios e sem o caso real
- extensão pgvector
- sonda `/saude/viva/`
- estados “Não configurado” para OpenAI e Anthropic

Chamadas reais a APIs de modelo não fazem parte dos testes.
