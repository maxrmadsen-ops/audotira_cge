import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("prestacoes_contas", "0004_estado_revisao_e_campos_monetarios"),
        ("laboratorio", "0003_rubrica_e_localizacao"),
    ]

    operations = [
        migrations.CreateModel(
            name="CadeiaConciliacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=80, verbose_name="código estável")),
                ("titulo", models.CharField(max_length=255, verbose_name="título")),
                ("criterio_item", models.TextField(blank=True, verbose_name="critério do item previsto")),
                ("verificacoes", models.JSONField(blank=True, default=list, verbose_name="verificações")),
                ("separacao", models.JSONField(blank=True, default=dict, verbose_name="separação das conclusões")),
                ("confianca", models.CharField(default="sugerida", max_length=20, verbose_name="qualidade da sugestão")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("sugerido", "Vínculo sugerido"),
                            ("confirmado", "Vínculo confirmado"),
                            ("rejeitado", "Vínculo rejeitado"),
                        ],
                        default="sugerido",
                        max_length=20,
                        verbose_name="revisão do vínculo",
                    ),
                ),
                ("justificativa", models.TextField(blank=True, verbose_name="justificativa")),
                ("revisado_em", models.DateTimeField(blank=True, null=True, verbose_name="revisado em")),
                (
                    "apoio",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cadeias_apoio",
                        to="laboratorio.regiaodocumental",
                        verbose_name="documento de apoio",
                    ),
                ),
                (
                    "comprovante",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cadeias_comprovante",
                        to="laboratorio.regiaodocumental",
                        verbose_name="comprovante sugerido",
                    ),
                ),
                (
                    "execucao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cadeias_execucao",
                        to="laboratorio.regiaodocumental",
                        verbose_name="documento de execução",
                    ),
                ),
                (
                    "item_plano",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cadeias_sugeridas",
                        to="prestacoes_contas.itemplanotrabalho",
                        verbose_name="item previsto sugerido",
                    ),
                ),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cadeias",
                        to="laboratorio.lotelaboratorio",
                        verbose_name="lote",
                    ),
                ),
                (
                    "revisado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cadeias_revisadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="revisado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "cadeia de conciliação",
                "verbose_name_plural": "cadeias de conciliação",
                "ordering": ["codigo"],
            },
        ),
        migrations.AddConstraint(
            model_name="cadeiaconciliacao",
            constraint=models.UniqueConstraint(fields=("lote", "codigo"), name="cadeia_unica_no_lote"),
        ),
    ]
