# regras

Catálogo e motor das regras de análise da CGE.

A fonte funcional é a planilha `Matriz_Tecnica_Regras_Analise_IA_2022TR929.xlsx`. O texto original está na semente `dados/matriz_regras_cge.json`. A planilha e os documentos reais não entram no Git.

O carregamento idempotente é `python manage.py carregar_regras_cge`.

A IA aponta fatos, evidências, cruzamentos e possíveis inconsistências. A conclusão cabe ao analista.
