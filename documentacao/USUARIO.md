# Uso

1. Abra `http://127.0.0.1:8080/entrar/`.
2. Entre com um dos usuários de desenvolvimento definidos no `.env`.
3. O painel mostra os indicadores previstos, ainda sem cálculo de regras ou análises.
4. Prestações de Contas lista, cadastra, edita e detalha o processo, com abas de visão geral, linha do tempo, plano, financeiro, folha e documentos.
5. Documentos recebe PDFs da prestação, processa em segundo plano e permite corrigir a classificação.
6. Normas cadastra a base de conhecimento, mostra vigência, trechos e a pesquisa normativa. A pesquisa não decide a prestação. Regras, análises, achados, pré-análises, avaliação e FinOps continuam “Em preparação”.
7. O administrador consulta a saúde do sistema e a trilha de auditoria. Só o administrador cadastra, versiona, reprocessa e desativa norma. Auditor, analista e consulta pesquisam e leem.
8. O perfil Consulta visualiza prestações, documentos e normas, e não altera registros.

O cenário sintético da prestação é carregado com `python manage.py carregar_cenario_demonstracao`. O perfil Consulta visualiza documentos e normas, e não envia nem reclassifica. Ainda não há regras nem pré-análise.
