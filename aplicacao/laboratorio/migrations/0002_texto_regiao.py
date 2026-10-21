from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("laboratorio", "0001_laboratorio_documental"),
    ]

    operations = [
        migrations.AddField(
            model_name="regiaodocumental",
            name="texto_regiao",
            field=models.TextField(blank=True, verbose_name="texto da região"),
        ),
        migrations.AddField(
            model_name="regiaodocumental",
            name="versao_extracao",
            field=models.CharField(blank=True, max_length=20, verbose_name="versão da extração"),
        ),
    ]
