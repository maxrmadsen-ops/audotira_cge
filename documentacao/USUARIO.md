# Uso

1. Abra `http://127.0.0.1:8080/entrar/`.
2. Entre com um dos usuários de desenvolvimento definidos no `.env`.
3. O painel mostra os indicadores previstos, ainda sem cálculo de regras ou análises.
4. Prestações de Contas lista, cadastra, edita e detalha o processo, com abas de visão geral, linha do tempo, plano, financeiro, folha e documentos.
5. Documentos recebe PDFs, processa em segundo plano e permite corrigir a classificação. Análises, achados, pré-análises, normas, regras, avaliação e FinOps continuam “Em preparação”.
6. O administrador consulta a saúde do sistema e a trilha de auditoria.
7. O perfil Consulta visualiza prestações e não altera registros.

O cenário sintético da prestação é carregado com `python manage.py carregar_cenario_demonstracao`. O perfil Consulta visualiza documentos e não envia nem reclassifica. Ainda não há normas, regras nem pré-análise.
