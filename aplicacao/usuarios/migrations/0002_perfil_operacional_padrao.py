# Generated manually for Onda 10.4.1 complementary checkpoint

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="perfil",
            field=models.CharField(
                choices=[
                    ("ADMINISTRADOR", "Administrador"),
                    ("AUDITOR", "Auditor"),
                    ("ANALISTA", "Analista"),
                    ("CONSULTA", "Consulta (legado)"),
                ],
                default="ANALISTA",
                max_length=20,
                verbose_name="perfil",
            ),
        ),
    ]
