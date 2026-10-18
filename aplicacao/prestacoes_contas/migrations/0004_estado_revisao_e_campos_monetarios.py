"""Alinha o estado do Django aos models, sem mudar colunas nem valores.

A opção "rejeitado" existe no model desde o Ciclo 5. Os quatro campos
monetários criados na 0003 foram registrados como DecimalField, enquanto
o model usa DinheiroField. Nos dois casos a coluna já é a definitiva:
varchar(30) para a revisão e numeric(16, 2) para o dinheiro.
"""

import aplicacao.prestacoes_contas.campos
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0003_revisao_plano_trabalho"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemplanotrabalho",
            name="status_revisao",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                    ("rejeitado", "Não correspondente"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão",
            ),
        ),
        migrations.AlterField(
            model_name="itemplanotrabalho",
            name="valor_unitario",
            field=aplicacao.prestacoes_contas.campos.DinheiroField(
                blank=True,
                decimal_places=2,
                max_digits=16,
                null=True,
                verbose_name="valor unitário",
            ),
        ),
        migrations.AlterField(
            model_name="meta",
            name="status_revisao",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                    ("rejeitado", "Não correspondente"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão",
            ),
        ),
        migrations.AlterField(
            model_name="planotrabalho",
            name="cronograma_status",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                    ("rejeitado", "Não correspondente"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão do cronograma",
            ),
        ),
        migrations.AlterField(
            model_name="planotrabalho",
            name="status_revisao",
            field=models.CharField(
                choices=[
                    ("aguardando_validacao", "Aguardando revisão"),
                    ("confirmado", "Confirmado"),
                    ("corrigido", "Corrigido"),
                    ("rejeitado", "Não correspondente"),
                ],
                default="confirmado",
                max_length=30,
                verbose_name="revisão",
            ),
        ),
        migrations.AlterField(
            model_name="planotrabalho",
            name="valor_contrapartida",
            field=aplicacao.prestacoes_contas.campos.DinheiroField(
                blank=True,
                decimal_places=2,
                max_digits=16,
                null=True,
                verbose_name="valor de contrapartida informado",
            ),
        ),
        migrations.AlterField(
            model_name="planotrabalho",
            name="valor_global",
            field=aplicacao.prestacoes_contas.campos.DinheiroField(
                blank=True,
                decimal_places=2,
                max_digits=16,
                null=True,
                verbose_name="valor global informado",
            ),
        ),
        migrations.AlterField(
            model_name="planotrabalho",
            name="valor_repasse",
            field=aplicacao.prestacoes_contas.campos.DinheiroField(
                blank=True,
                decimal_places=2,
                max_digits=16,
                null=True,
                verbose_name="valor de repasse informado",
            ),
        ),
    ]
