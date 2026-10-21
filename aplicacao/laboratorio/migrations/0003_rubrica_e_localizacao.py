import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("laboratorio", "0002_texto_regiao"),
    ]

    operations = [
        migrations.AddField(
            model_name="campoextraido",
            name="evidencia_altura",
            field=models.FloatField(blank=True, null=True, verbose_name="altura da evidência"),
        ),
        migrations.AddField(
            model_name="campoextraido",
            name="evidencia_largura",
            field=models.FloatField(blank=True, null=True, verbose_name="largura da evidência"),
        ),
        migrations.AddField(
            model_name="campoextraido",
            name="evidencia_x",
            field=models.FloatField(blank=True, null=True, verbose_name="x da evidência"),
        ),
        migrations.AddField(
            model_name="campoextraido",
            name="evidencia_y",
            field=models.FloatField(blank=True, null=True, verbose_name="y da evidência"),
        ),
        migrations.AddField(
            model_name="campoextraido",
            name="localizacao_precisa",
            field=models.BooleanField(default=False, verbose_name="localização precisa"),
        ),
        migrations.CreateModel(
            name="RubricaExtraida",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordem", models.PositiveIntegerField(default=1, verbose_name="ordem")),
                ("codigo", models.CharField(blank=True, max_length=10, verbose_name="código")),
                ("descricao", models.CharField(blank=True, max_length=180, verbose_name="descrição")),
                ("referencia", models.CharField(blank=True, max_length=40, verbose_name="referência")),
                ("unidade", models.CharField(blank=True, max_length=20, verbose_name="unidade da referência")),
                ("natureza", models.CharField(choices=[("provento", "Provento"), ("desconto", "Desconto")], max_length=20, verbose_name="natureza")),
                ("valor_original", models.CharField(blank=True, max_length=40, verbose_name="valor original")),
                ("valor_normalizado", models.CharField(blank=True, max_length=40, verbose_name="valor normalizado")),
                ("trecho_evidencia", models.TextField(blank=True, verbose_name="trecho de evidência")),
                ("evidencia_x", models.FloatField(blank=True, null=True, verbose_name="x da evidência")),
                ("evidencia_y", models.FloatField(blank=True, null=True, verbose_name="y da evidência")),
                ("evidencia_largura", models.FloatField(blank=True, null=True, verbose_name="largura da evidência")),
                ("evidencia_altura", models.FloatField(blank=True, null=True, verbose_name="altura da evidência")),
                ("localizacao_precisa", models.BooleanField(default=False, verbose_name="localização precisa")),
                ("metodo", models.CharField(blank=True, max_length=60, verbose_name="método")),
                ("estado_confianca", models.CharField(blank=True, max_length=40, verbose_name="estado de confiança")),
                (
                    "estado_revisao",
                    models.CharField(
                        choices=[
                            ("pendente", "Extração pendente de revisão"),
                            ("confirmado", "Extração confirmada"),
                            ("corrigido", "Extração corrigida"),
                            ("ausente", "Não localizado na evidência"),
                            ("ilegivel", "Marcado como ilegível"),
                        ],
                        default="pendente",
                        max_length=20,
                        verbose_name="estado da revisão",
                    ),
                ),
                ("historico_correcoes", models.JSONField(blank=True, default=list, verbose_name="histórico de correções")),
                ("revisado_em", models.DateTimeField(blank=True, null=True, verbose_name="revisado em")),
                (
                    "regiao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rubricas",
                        to="laboratorio.regiaodocumental",
                        verbose_name="região",
                    ),
                ),
                (
                    "revisado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rubricas_laboratorio_revisadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="revisado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "rubrica extraída",
                "verbose_name_plural": "rubricas extraídas",
                "ordering": ["ordem", "id"],
            },
        ),
    ]
