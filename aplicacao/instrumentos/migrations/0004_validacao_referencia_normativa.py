import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("instrumentos", "0003_rotulo_campo_corrigido"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="referencianormativaextraida",
            name="validado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="validado em"),
        ),
        migrations.AddField(
            model_name="referencianormativaextraida",
            name="validado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="referencias_normativas_validadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="validado por",
            ),
        ),
    ]
