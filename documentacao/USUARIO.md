# Uso

1. Abra `http://127.0.0.1:8080/entrar/`.
2. Entre com um usuário operacional (Administrador, Auditor ou Analista) definido no `.env` ou com os usuários de homologação.
3. O Painel abre a Visão 360° e as abas da jornada da auditoria. Ele mostra o que já foi gravado. A investigação continua nos menus. O FinOps, em menu próprio, mostra tokens e custo quando há preço cadastrado.
4. Prestações de Contas lista, cadastra, edita e detalha o processo. Administrador e Auditor veem todos os processos. O Analista vê somente os atribuídos a ele. A aba Análise executa o motor e mostra resultado, fontes e cálculo. A síntese não conclui a prestação.
5. Documentos recebe PDFs da prestação atribuída, processa em segundo plano e permite corrigir a classificação preservando o valor originalmente extraído. Em cada prestação, Preparar instrumento da parceria abre o passo 1 da preparação da análise. O detalhe está em `PREPARACAO_ANALISE.md`.
6. Normas, Regras, Inteligência Artificial, Achados, Pré-análises, Avaliação e FinOps seguem a jornada já implementada. O Analista opera apenas nos processos sob sua responsabilidade.
7. O Administrador gerencia usuários em `/administracao/usuarios/`, consulta saúde, trilha de auditoria, provedores, modelos e prompts. O Auditor distribui e redistribui processos e não administra usuários.
8. Detalhes da matriz de perfis: `PERFIS_E_RESPONSABILIDADE.md`.

O cenário sintético da prestação é carregado com `python manage.py carregar_cenario_demonstracao`. O catálogo é carregado com `python manage.py carregar_regras_cge`. A pré-análise e a IA não aprovam nem reprovam a prestação.
