from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("instrumentos", "0002_preparacao_instrumento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campoinstrumento",
            name="status",
            field=models.CharField(
                choices=[
                    ("extraido", "Extraído"),
                    ("aguardando_validacao", "Pendente de validação"),
                    ("validado", "Validado"),
                    ("corrigido", "Corrigido pelo analista"),
                    ("nao_identificado", "Não identificado"),
                    ("rejeitado", "Rejeitado"),
                ],
                default="aguardando_validacao",
                max_length=30,
                verbose_name="status",
            ),
        ),
    ]
