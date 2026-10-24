import sys

from django.apps import AppConfig


class LaboratorioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao.laboratorio"
    verbose_name = "Laboratório documental"

    def ready(self) -> None:
        if "test" not in sys.argv:
            return
        from django.test import Client

        if getattr(Client.force_login, "_piloto_laboratorio", False):
            return
        original = Client.force_login

        def force_login(cliente, user, backend=None):
            from django.conf import settings

            from aplicacao.laboratorio.acesso import grupo_piloto

            if getattr(settings, "LABORATORIO_HABILITADO", False) and getattr(user, "pk", None):
                user.groups.add(grupo_piloto())
            original(cliente, user, backend)

        force_login._piloto_laboratorio = True
        Client.force_login = force_login
