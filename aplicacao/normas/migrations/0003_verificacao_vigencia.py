import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("instrumentos", "0004_validacao_referencia_normativa"),
        ("normas", "0002_situacao_nao_verificada"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VerificacaoVigencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("nao_verificada", "Não verificada"),
                            ("datas_informadas", "Datas informadas"),
                            ("verificada", "Vigência verificada"),
                            ("divergencia", "Divergência de vigência"),
                        ],
                        default="nao_verificada",
                        max_length=20,
                        verbose_name="estado da verificação",
                    ),
                ),
                ("inicio_vigencia", models.DateField(blank=True, null=True, verbose_name="início informado")),
                ("fim_vigencia", models.DateField(blank=True, null=True, verbose_name="fim informado")),
                ("fonte_documental", models.TextField(blank=True, verbose_name="fonte documental")),
                ("data_referencia", models.DateField(blank=True, null=True, verbose_name="data de referência da análise")),
                ("fundamentacao", models.TextField(blank=True, verbose_name="fundamentação")),
                ("motivo_divergencia", models.TextField(blank=True, verbose_name="motivo da divergência")),
                ("versao_documento", models.PositiveIntegerField(verbose_name="versão do documento")),
                ("hash_sha256", models.CharField(max_length=64, verbose_name="hash do documento")),
                ("verificado_em", models.DateTimeField(blank=True, null=True, verbose_name="verificado em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                (
                    "criado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vigencias_registradas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="registrado por",
                    ),
                ),
                (
                    "norma",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="verificacoes_vigencia",
                        to="normas.norma",
                        verbose_name="norma",
                    ),
                ),
                (
                    "termo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verificacoes_vigencia",
                        to="instrumentos.termofomento",
                        verbose_name="termo",
                    ),
                ),
                (
                    "verificado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vigencias_verificadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="verificado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "verificação de vigência",
                "verbose_name_plural": "verificações de vigência",
                "ordering": ["-criado_em", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="verificacaovigencia",
            constraint=models.CheckConstraint(
                condition=models.Q(fim_vigencia__isnull=True)
                | models.Q(inicio_vigencia__isnull=True)
                | models.Q(fim_vigencia__gte=models.F("inicio_vigencia")),
                name="verificacao_vigencia_coerente",
            ),
        ),
    ]
