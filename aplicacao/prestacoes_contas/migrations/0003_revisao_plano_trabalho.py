import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0002_fundamento_classificacao"),
        ("prestacoes_contas", "0002_perfis_responsabilidade"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="planotrabalho",
            name="documento",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="planos_extraidos",
                to="documentos.documento",
                verbose_name="documento de origem",
            ),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="objeto",
            field=models.TextField(blank=True, verbose_name="objeto"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="finalidade",
            field=models.TextField(blank=True, verbose_name="finalidade"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="transferencia",
            field=models.CharField(blank=True, max_length=40, verbose_name="transferência"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="proponente",
            field=models.CharField(blank=True, max_length=255, verbose_name="proponente"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="unidade_gestora",
            field=models.CharField(blank=True, max_length=255, verbose_name="unidade gestora"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="publico_alvo",
            field=models.CharField(blank=True, max_length=255, verbose_name="público alvo"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="situacao_informada",
            field=models.CharField(blank=True, max_length=80, verbose_name="situação informada no documento"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="valor_global",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True, verbose_name="valor global informado"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="valor_repasse",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True, verbose_name="valor de repasse informado"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="valor_contrapartida",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True, verbose_name="valor de contrapartida informado"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="status_revisao",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão",
            ),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="revisado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="planos_revisados",
                to=settings.AUTH_USER_MODEL,
                verbose_name="revisado por",
            ),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="revisado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="revisado em"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="evidencias",
            field=models.JSONField(blank=True, default=dict, verbose_name="evidências da identificação"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="cronograma",
            field=models.JSONField(blank=True, default=list, verbose_name="cronograma extraído"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="cronograma_status",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão do cronograma",
            ),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="documento",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="itens_plano_extraidos",
                to="documentos.documento",
                verbose_name="documento de origem",
            ),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="descricao_original",
            field=models.TextField(blank=True, verbose_name="descrição original"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="classificacao_orcamentaria",
            field=models.CharField(blank=True, max_length=160, verbose_name="classificação orçamentária"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="tipo_despesa",
            field=models.CharField(blank=True, max_length=80, verbose_name="tipo de despesa no documento"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="recurso",
            field=models.CharField(blank=True, max_length=80, verbose_name="recurso"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="valor_unitario",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True, verbose_name="valor unitário"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="pagina",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="página"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="trecho",
            field=models.TextField(blank=True, verbose_name="trecho de origem"),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="status_revisao",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão",
            ),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="revisado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="itens_plano_revisados",
                to=settings.AUTH_USER_MODEL,
                verbose_name="revisado por",
            ),
        ),
        migrations.AddField(
            model_name="itemplanotrabalho",
            name="revisado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="revisado em"),
        ),
        migrations.AddField(
            model_name="meta",
            name="documento",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="metas_plano_extraidas",
                to="documentos.documento",
                verbose_name="documento de origem",
            ),
        ),
        migrations.AddField(
            model_name="meta",
            name="descricao_original",
            field=models.TextField(blank=True, verbose_name="descrição original"),
        ),
        migrations.AddField(
            model_name="meta",
            name="forma_execucao",
            field=models.TextField(blank=True, verbose_name="forma de execução"),
        ),
        migrations.AddField(
            model_name="meta",
            name="parametros_afericao",
            field=models.TextField(blank=True, verbose_name="parâmetros de aferição"),
        ),
        migrations.AddField(
            model_name="meta",
            name="etapas",
            field=models.TextField(blank=True, verbose_name="etapas"),
        ),
        migrations.AddField(
            model_name="meta",
            name="pagina",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="página"),
        ),
        migrations.AddField(
            model_name="meta",
            name="trecho",
            field=models.TextField(blank=True, verbose_name="trecho de origem"),
        ),
        migrations.AddField(
            model_name="meta",
            name="status_revisao",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão",
            ),
        ),
        migrations.AddField(
            model_name="meta",
            name="revisado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="metas_plano_revisadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="revisado por",
            ),
        ),
        migrations.AddField(
            model_name="meta",
            name="revisado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="revisado em"),
        ),
    ]
