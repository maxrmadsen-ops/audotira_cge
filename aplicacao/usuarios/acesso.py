"""Regras de acesso da fundação. O controle vale no backend, não só no menu."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from aplicacao.usuarios.models import Usuario

PERFIS_OPERACIONAIS = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)

PERFIS_VISAO_TRANSVERSAL = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    # Legado: leitura transversal somente. Não atribuível na interface.
    Usuario.Perfil.CONSULTA,
)

# Valor legado no banco. Não é persona operacional nem atribuível na interface.
PERFIS_OPERACIONAIS_ATRIBUIVEIS = PERFIS_OPERACIONAIS


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


def pode_gerenciar_usuarios(usuario) -> bool:
    return pode_administrar(usuario)


def pode_distribuir_processos(usuario) -> bool:
    return pode_consultar(usuario) and usuario.perfil in {
        Usuario.Perfil.ADMINISTRADOR,
        Usuario.Perfil.AUDITOR,
    }


def possui_visao_transversal(usuario) -> bool:
    return pode_consultar(usuario) and usuario.perfil in PERFIS_VISAO_TRANSVERSAL


def _eh_analista_responsavel(usuario, prestacao) -> bool:
    if usuario.perfil != Usuario.Perfil.ANALISTA:
        return False
    responsavel_id = getattr(prestacao, "analista_responsavel_id", None)
    return bool(responsavel_id and responsavel_id == usuario.pk)


def pode_ver_prestacao(usuario, prestacao) -> bool:
    if not pode_consultar(usuario):
        return False
    if possui_visao_transversal(usuario):
        return True
    if usuario.perfil == Usuario.Perfil.ANALISTA:
        return _eh_analista_responsavel(usuario, prestacao)
    return False


def pode_atuar_na_prestacao(usuario, prestacao) -> bool:
    """Mutação operacional: admin/auditor em qualquer processo; analista só no próprio."""
    if not pode_executar_analise(usuario):
        return False
    if usuario.perfil in {Usuario.Perfil.ADMINISTRADOR, Usuario.Perfil.AUDITOR}:
        return True
    return _eh_analista_responsavel(usuario, prestacao)


def exigir_ver_prestacao(usuario, prestacao) -> None:
    if not pode_ver_prestacao(usuario, prestacao):
        raise PermissionDenied("Processo não disponível para este perfil.")


def exigir_atuar_na_prestacao(usuario, prestacao) -> None:
    if not pode_atuar_na_prestacao(usuario, prestacao):
        raise PermissionDenied("Sem permissão para alterar este processo.")


def prestacoes_visiveis(usuario, queryset: QuerySet | None = None) -> QuerySet:
    from aplicacao.prestacoes_contas.models import PrestacaoContas

    base = queryset if queryset is not None else PrestacaoContas.objects.all()
    if not pode_consultar(usuario):
        return base.none()
    if possui_visao_transversal(usuario):
        return base
    if usuario.perfil == Usuario.Perfil.ANALISTA:
        return base.filter(analista_responsavel=usuario)
    return base.none()


class PerfilExigidoMixin(LoginRequiredMixin, UserPassesTestMixin):
    perfis_permitidos: tuple[str, ...] = ()

    def test_func(self) -> bool:
        return pode_consultar(self.request.user) and self.request.user.perfil in self.perfis_permitidos
