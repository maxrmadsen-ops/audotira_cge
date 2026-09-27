# Uso

1. Abra `http://127.0.0.1:8080/entrar/`.
2. Entre com um dos usuários de desenvolvimento definidos no `.env`.
3. O painel mostra a base normativa e mantém os indicadores de achados e esforço para as próximas ondas.
4. Prestações de Contas lista, cadastra, edita e detalha o processo. A aba Análise executa o motor em modo normal ou em teste cego e mostra resultado, fontes, cálculos e limitação. A síntese não conclui a prestação.
5. Documentos recebe PDFs da prestação, processa em segundo plano e permite corrigir a classificação.
6. Normas cadastra a base de conhecimento, mostra vigência, trechos e a pesquisa normativa. A pesquisa não decide a prestação. Regras lista as 89 regras, com o texto original da matriz e a classificação técnica. O Laboratório de IA compara dois modelos sem alterar a análise oficial. Achados lista potenciais, evidências e revisão humana. Pré-análises mostra a versão técnica, as fontes e a revisão humana. Avaliação abre o Ground Truth e a comparação IA × técnico. FinOps continua “Em preparação”.
7. O administrador consulta a saúde do sistema, a trilha de auditoria, provedores, modelos, prompts, preços, limites e o consumo instrumental. A chave não aparece na tela. Só o administrador cadastra, versiona, reprocessa e desativa norma. Auditor, analista e consulta pesquisam e leem.
8. O perfil Consulta visualiza prestações, documentos, normas, o catálogo e o resultado da análise. Não executa a análise nem altera registros.

O cenário sintético da prestação é carregado com `python manage.py carregar_cenario_demonstracao`. O catálogo é carregado com `python manage.py carregar_regras_cge`. O perfil Consulta visualiza documentos e normas, e não envia nem reclassifica. Ainda não há pré-análise.
