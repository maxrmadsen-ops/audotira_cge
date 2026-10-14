from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("normas", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="norma",
            name="situacao",
            field=models.CharField(
                choices=[
                    ("vigente", "Vigente"),
                    ("revogada", "Revogada"),
                    ("substituida", "Substituída"),
                    ("alterada", "Alterada"),
                    ("nao_verificada", "Não verificada"),
                ],
                default="vigente",
                max_length=20,
                verbose_name="situação",
            ),
        ),
    ]
