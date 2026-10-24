"""Acesso ao laboratório documental. A flag desligada vale para qualquer usuário."""

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from aplicacao.usuarios.acesso import PERFIS_OPERACIONAIS, PerfilExigidoMixin, pode_executar_analise

GRUPO_PILOTO = "CGE_LABORATORIO_PILOTO"


def laboratorio_habilitado() -> bool:
    return bool(getattr(settings, "LABORATORIO_HABILITADO", False))


def grupo_piloto() -> Group:
    grupo, _ = Group.objects.get_or_create(name=GRUPO_PILOTO)
    return grupo


def pode_abrir_laboratorio(usuario) -> bool:
    """Flag, grupo piloto e perfil operacional. Superusuário não contorna a flag."""
    if not laboratorio_habilitado():
        return False
    if not pode_executar_analise(usuario):
        return False
    return usuario.groups.filter(name=GRUPO_PILOTO).exists()


def exigir_laboratorio(usuario) -> None:
    if not pode_abrir_laboratorio(usuario):
        raise PermissionDenied("Laboratório indisponível para este usuário.")


class AcessoLaboratorioMixin(PerfilExigidoMixin):
    """Exige login, flag, grupo piloto e um perfil que já podia operar o processo."""

    perfis_permitidos = PERFIS_OPERACIONAIS

    def test_func(self) -> bool:
        if not pode_abrir_laboratorio(self.request.user):
            return False
        return super().test_func()
