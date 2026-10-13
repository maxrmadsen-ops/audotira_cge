import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0002_fundamento_classificacao"),
        ("instrumentos", "0001_termo_fomento_e_prompt"),
        ("prestacoes_contas", "0002_perfis_responsabilidade"),
    ]

    operations = [
        migrations.CreateModel(
            name="PreparacaoInstrumento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado", models.CharField(choices=[("nao_iniciado", "Não iniciado"), ("em_processamento", "Em processamento"), ("extracao_concluida", "Extração concluída"), ("aguardando_validacao", "Aguardando validação"), ("validado", "Validado"), ("requer_atencao", "Requer atenção"), ("erro", "Erro")], default="nao_iniciado", max_length=32, verbose_name="estado")),
                ("mensagem", models.CharField(blank=True, max_length=255, verbose_name="mensagem")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("documento", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="preparacoes", to="documentos.documento", verbose_name="instrumento")),
                ("prestacao", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="preparacao_instrumento", to="prestacoes_contas.prestacaocontas", verbose_name="prestação de contas")),
            ],
            options={
                "verbose_name": "preparação do instrumento",
                "verbose_name_plural": "preparações do instrumento",
            },
        ),
    ]
