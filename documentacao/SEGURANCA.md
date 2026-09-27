# Segurança

- Segredos ficam no `.env`, fora do Git.
- `Chave auditoria_cge.txt` está no `.gitignore` e não deve ser versionado.
- PostgreSQL e Redis não publicam porta no host.
- CSRF, cookies `HttpOnly` e `X-Frame-Options: DENY` estão ativos.
- Com `DEBUG=False`, os cookies de sessão e CSRF passam a exigir HTTPS.
- O redirecionamento HTTPS e o endurecimento final ficam na Onda 10, para não impedir o uso local em HTTP.
- Falhas de login gravam apenas o nome de usuário informado, nunca a senha.
- Registros de auditoria não podem ser alterados nem apagados pela administração técnica.
- Os PDFs da prestação ficam em volume interno (`arquivos/documentos`), fora do Nginx. O download passa por view autenticada, com nome físico aleatório e recusa de caminho que tente sair da raiz.
- A trilha de upload, processamento e validação não grava o texto integral do documento.
- O PDF normativo fica em `arquivos/normas`, separado dos documentos da prestação. O download também passa por view autenticada.
- Texto extraído de norma é dado indexável. Frases dentro do PDF não são executadas como instrução.
- A consulta normativa registra filtros, normas elegíveis e scores, sem segredo e sem o arquivo.
- Chaves de OpenAI e Anthropic ficam só no `.env`. Não entram no banco, no log, no prompt versionado nem na tela de saúde.
- O log de IA grava identificador de uso, provedor, modelo, status, tokens e latência. Não grava chave, cabeçalho Authorization nem prompt completo.
- Documento excluído no teste cego não entra no contexto enviado ao provedor.
- Ground Truth, parecer anterior e resposta esperada são descartados antes da chamada.
- Texto de documento é dado, não instrução.
- A resposta da IA permanece pendente de validação humana. O laboratório não grava a execução oficial da regra.

O `.env.example` contém somente placeholders. Senhas e chaves efetivas ficam no `.env`.
