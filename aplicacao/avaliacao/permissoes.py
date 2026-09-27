"""A permissão administrativa não equivale a autoridade técnica nesta onda."""

from aplicacao.usuarios.acesso import pode_consultar
from aplicacao.usuarios.models import Usuario


def _perfil(usuario, perfis: set[str]) -> bool:
    return pode_consultar(usuario) and usuario.perfil in perfis


def pode_ler_avaliacao(usuario) -> bool:
    return pode_consultar(usuario)


def pode_colaborar_ground_truth(usuario) -> bool:
    return _perfil(usuario, {Usuario.Perfil.ANALISTA, Usuario.Perfil.AUDITOR})


def pode_validar_ground_truth(usuario) -> bool:
    return _perfil(usuario, {Usuario.Perfil.AUDITOR})


def pode_congelar_ground_truth(usuario) -> bool:
    return _perfil(usuario, {Usuario.Perfil.AUDITOR})


def pode_revisar_correspondencia(usuario) -> bool:
    return _perfil(usuario, {Usuario.Perfil.AUDITOR})


def pode_concluir_avaliacao(usuario) -> bool:
    return _perfil(usuario, {Usuario.Perfil.AUDITOR})
