"""Regras de acesso da fundação. O controle vale no backend, não só no menu."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from aplicacao.usuarios.models import Usuario


def pode_consultar(usuario) -> bool:
    return bool(
        getattr(usuario, "is_authenticated", False)
        and usuario.perfil in Usuario.Perfil.values
    )


def pode_executar_analise(usuario) -> bool:
    return pode_consultar(usuario) and usuario.perfil in {
        Usuario.Perfil.ADMINISTRADOR,
        Usuario.Perfil.AUDITOR,
        Usuario.Perfil.ANALISTA,
    }


def pode_validar_analise(usuario) -> bool:
    return pode_consultar(usuario) and usuario.perfil in {
        Usuario.Perfil.ADMINISTRADOR,
        Usuario.Perfil.AUDITOR,
    }


def pode_administrar(usuario) -> bool:
    return pode_consultar(usuario) and usuario.perfil == Usuario.Perfil.ADMINISTRADOR


class PerfilExigidoMixin(LoginRequiredMixin, UserPassesTestMixin):
    perfis_permitidos: tuple[str, ...] = ()

    def test_func(self) -> bool:
        return pode_consultar(self.request.user) and self.request.user.perfil in self.perfis_permitidos
