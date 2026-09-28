from django.db import migrations, models

TIPOS = [
    ("termo", "Termo"),
    ("plano_trabalho", "Plano de trabalho"),
    ("prestacao_parcial", "Prestação parcial"),
    ("prestacao_final", "Prestação final"),
    ("folha_pagamento", "Folha de pagamento"),
    ("nota_fiscal", "Nota fiscal"),
    ("recibo", "Recibo"),
    ("comprovante_bancario", "Comprovante bancário"),
    ("extrato_bancario", "Extrato bancário"),
    ("guia", "Guia"),
    ("relatorio_sigef", "Relatório SIGEF"),
    ("cadastro_entidade", "Cadastro de entidade"),
    ("relatorio_execucao", "Relatório de execução"),
    ("declaracao", "Declaração"),
    ("outro", "Outro"),
    ("nao_classificado", "Não identificado"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("documentos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documento",
            name="fundamento_classificacao",
            field=models.TextField(blank=True, verbose_name="fundamento da classificação"),
        ),
        migrations.AlterField(
            model_name="documento",
            name="tipo_documento",
            field=models.CharField(
                choices=TIPOS,
                default="nao_classificado",
                max_length=40,
                verbose_name="tipo",
            ),
        ),
        migrations.AlterField(
            model_name="documento",
            name="classificacao_original",
            field=models.CharField(
                blank=True,
                choices=TIPOS,
                max_length=40,
                verbose_name="classificação original",
            ),
        ),
        migrations.AlterField(
            model_name="documento",
            name="tipo_sugerido",
            field=models.CharField(
                blank=True,
                choices=TIPOS,
                max_length=40,
                verbose_name="tipo sugerido",
            ),
        ),
        migrations.AlterField(
            model_name="documento",
            name="metodo_classificacao",
            field=models.CharField(
                choices=[
                    ("nome_arquivo", "Nome do arquivo"),
                    ("palavras_chave", "Palavras-chave"),
                    ("heuristica", "Heurística"),
                    ("estrutural", "Evidência estrutural"),
                    ("humano", "Validação humana"),
                    ("nenhum", "Nenhum"),
                ],
                default="nenhum",
                max_length=30,
                verbose_name="método de classificação",
            ),
        ),
    ]
