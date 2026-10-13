"""Cria usuários de homologação por perfil. Senha vem só do ambiente."""

import os

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from aplicacao.usuarios.models import Usuario

USUARIOS_HOMOLOGACAO = (
    ("adm_cedro", Usuario.Perfil.ADMINISTRADOR, True, "Administrador de homologação"),
    ("aud_ipe", Usuario.Perfil.AUDITOR, False, "Auditor de homologação"),
    ("ana_araucaria", Usuario.Perfil.ANALISTA, False, "Analista de homologação"),
)


class Command(BaseCommand):
    help = (
        "Cria usuários de homologação (adm_cedro, aud_ipe, ana_araucaria). "
        "A senha inicial vem de SENHA_HOMOLOGACAO no ambiente e não é impressa."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--atualizar-senha",
            action="store_true",
            help="Atualiza a senha dos usuários já existentes com SENHA_HOMOLOGACAO.",
        )

    def handle(self, *args, **options):
        senha = os.environ.get("SENHA_HOMOLOGACAO", "").strip()
        if not senha:
            raise CommandError("Defina SENHA_HOMOLOGACAO no ambiente. A senha não pode ser vazia.")

        for username, perfil, superusuario, finalidade in USUARIOS_HOMOLOGACAO:
            grupo, _ = Group.objects.get_or_create(name=perfil)
            usuario, criado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "perfil": perfil,
                    "is_staff": superusuario,
                    "is_superuser": superusuario,
                    "is_active": True,
                    "first_name": finalidade,
                },
            )
            if criado:
                usuario.set_password(senha)
                usuario.save()
                self.stdout.write(self.style.SUCCESS(f"Usuário de homologação criado: {username} ({perfil})"))
            else:
                campos = []
                if usuario.perfil != perfil:
                    usuario.perfil = perfil
                    campos.append("perfil")
                if usuario.is_staff != superusuario:
                    usuario.is_staff = superusuario
                    campos.append("is_staff")
                if usuario.is_superuser != superusuario:
                    usuario.is_superuser = superusuario
                    campos.append("is_superuser")
                if not usuario.is_active:
                    usuario.is_active = True
                    campos.append("is_active")
                if options["atualizar_senha"]:
                    usuario.set_password(senha)
                    campos.append("password")
                if campos:
                    usuario.save(update_fields=campos)
                    self.stdout.write(f"Usuário de homologação atualizado: {username} ({', '.join(campos)})")
                else:
                    self.stdout.write(f"Usuário de homologação já existia: {username} ({perfil})")
            usuario.groups.add(grupo)
        self.stdout.write("Homologação: senha inicial definida via ambiente. Troque antes de produção.")
