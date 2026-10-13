"""Aplica o escopo de perfil aos filtros do Painel 360°."""

from __future__ import annotations

from aplicacao.painel.consultas.filtros import FiltrosPainel
from aplicacao.usuarios.acesso import possui_visao_transversal, prestacoes_visiveis


def filtros_com_escopo(usuario, filtros: FiltrosPainel) -> FiltrosPainel:
    """Admin/Auditor: todos. Analista: somente processos atribuídos."""
    if possui_visao_transversal(usuario):
        return filtros.alterar(ids_prestacao=None)
    ids = tuple(prestacoes_visiveis(usuario).values_list("pk", flat=True))
    return filtros.alterar(ids_prestacao=ids)
