# Inteligência documental

O processamento não usa modelo de linguagem. A decisão administrativa continua com o auditor.

## Fluxo

1. Upload individual ou múltiplo, associado à prestação e, se informado, à prestação parcial.
2. Validação de extensão, conteúdo `%PDF`, arquivo vazio e tamanho máximo.
3. Gravação em `arquivos/documentos/<prestação>/<uuid>.pdf`.
4. SHA-256. Duplicidade gera alerta e auditoria, sem bloquear o envio.
5. Tarefa Celery `documentos.processar_documento`.
6. Texto nativo por página com pypdf.
7. Se a qualidade for ausente, insuficiente ou ilegível, OCR local com Tesseract (`por`) e Poppler.
8. Classificação heurística por nome e palavras-chave. Sem sinal suficiente, o tipo fica “Não classificado”.
9. Metadados candidatos (data, CPF, CNPJ, valor, números), com página, trecho e método.
10. Status “Aguardando validação” até um analista, auditor ou administrador confirmar ou corrigir o tipo.
11. A sugestão original permanece gravada depois da correção humana.

## OCR

Os limiares ficam na configuração: `OCR_MINIMO_CARACTERES` (40), `OCR_MINIMO_PALAVRAS` (8) e `OCR_LIMIAR_LEGIBILIDADE` (0,6). Página com texto utilizável não é enviada ao OCR. Falha de OCR em uma página fica registrada nela e não derruba as demais.

## Arquivos

O Nginx só publica `/static/`. O PDF é lido por uma view autenticada. O nome original do usuário não entra no caminho físico.

## Reprocessamento

A ação pede o pipeline de novo, substitui páginas e candidatos e grava quem solicitou, quando, o motivo e o resultado. A classificação original e, se já houver, a validação humana do tipo são preservadas.

## Rastreabilidade

Cada `DadoExtraidoDocumento` aponta para o documento, a página e o trecho que o originou, com o método `expressao_regular`. Isso prepara a evidência da Onda 6, que ainda não existe.
