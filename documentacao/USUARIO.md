# Uso

1. Abra `http://127.0.0.1:8080/entrar/`.
2. Entre com um dos usuários de desenvolvimento definidos no `.env`.
3. O Painel abre a Visão 360° e as abas da jornada da auditoria. Ele mostra o que já foi gravado. A investigação continua nos menus. O FinOps, em menu próprio, mostra tokens e custo quando há preço cadastrado.
4. Prestações de Contas lista, cadastra, edita e detalha o processo. A aba Análise executa o motor em modo normal ou em teste cego e mostra resultado, fontes, cálculos e limitação. A síntese não conclui a prestação.
5. Documentos recebe PDFs da prestação, processa em segundo plano e permite corrigir a classificação.
6. Normas cadastra a base de conhecimento, mostra vigência, trechos e a pesquisa normativa. A pesquisa não decide a prestação. Regras lista as 89 regras, com o texto original da matriz e a classificação técnica. Inteligência Artificial abre a visão geral; o Laboratório continua disponível ao administrador e não altera a análise oficial. Achados lista potenciais, evidências e revisão humana. Pré-análises mostra a versão técnica, as fontes e a revisão humana. Avaliação abre o Ground Truth e a comparação IA × técnico. FinOps mostra consumo e custo. Sem preço vigente, o custo aparece como não disponível.
7. O administrador consulta a saúde do sistema, a trilha de auditoria, provedores, modelos, prompts, preços, limites e o consumo instrumental. A chave não aparece na tela. Só o administrador cadastra, versiona, reprocessa e desativa norma. Auditor, analista e consulta pesquisam e leem.
8. O perfil Consulta visualiza prestações, documentos, normas, o catálogo e o resultado da análise. Não executa a análise nem altera registros.

O cenário sintético da prestação é carregado com `python manage.py carregar_cenario_demonstracao`. O catálogo é carregado com `python manage.py carregar_regras_cge`. O perfil Consulta visualiza o Painel, o FinOps, documentos e normas, e não envia, não reclassifica, não administra e não abre a saúde nem o laboratório. A pré-análise não aprova nem reprova a prestação.
