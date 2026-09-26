"""Cria os usuários de teste da fundação. Idempotente e sem senha fixa no código."""

import os

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from aplicacao.usuarios.models import Usuario

USUARIOS_INICIAIS = (
    ("USUARIO_ADMIN", "USUARIO_ADMIN_SENHA", "admin", Usuario.Perfil.ADMINISTRADOR, True),
    ("USUARIO_AUDITOR", "USUARIO_AUDITOR_SENHA", "auditor", Usuario.Perfil.AUDITOR, False),
    ("USUARIO_ANALISTA", "USUARIO_ANALISTA_SENHA", "analista", Usuario.Perfil.ANALISTA, False),
    ("USUARIO_CONSULTA", "USUARIO_CONSULTA_SENHA", "consulta", Usuario.Perfil.CONSULTA, False),
)


class Command(BaseCommand):
    help = "Cria os perfis iniciais de teste a partir das variáveis de ambiente."

    def handle(self, *args, **options):
        for variavel_usuario, variavel_senha, usuario_padrao, perfil, superusuario in USUARIOS_INICIAIS:
            username = os.environ.get(variavel_usuario, usuario_padrao).strip() or usuario_padrao
            senha = os.environ.get(variavel_senha, "").strip()
            if not senha:
                raise CommandError(f"Defina {variavel_senha} no ambiente.")

            grupo, _ = Group.objects.get_or_create(name=perfil)
            usuario, criado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "perfil": perfil,
                    "is_staff": superusuario,
                    "is_superuser": superusuario,
                    "is_active": True,
                    "first_name": perfil.label,
                },
            )
            if criado:
                usuario.set_password(senha)
                usuario.save()
                self.stdout.write(self.style.SUCCESS(f"Usuário criado: {username} ({perfil})"))
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
                if campos:
                    usuario.save(update_fields=campos)
                self.stdout.write(f"Usuário já existia: {username} ({perfil})")
            usuario.groups.add(grupo)
