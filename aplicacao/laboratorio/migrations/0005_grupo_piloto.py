from django.db import migrations


GRUPO = "CGE_LABORATORIO_PILOTO"


def criar_grupo(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=GRUPO)


def remover_grupo(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=GRUPO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0001_initial"),
        ("laboratorio", "0004_cadeia_conciliacao"),
    ]

    operations = [
        migrations.RunPython(criar_grupo, remover_grupo),
    ]
