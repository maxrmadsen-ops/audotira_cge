"""Monta a identificação dos envolvidos a partir do cadastro e das extrações."""

from __future__ import annotations


def montar_identificacao(prestacao) -> dict:
    termo = (
        _termo_da_prestacao(prestacao)
    )
    partes = list(termo.partes.all()) if termo is not None else []
    concedente_extraido = next((p for p in partes if p.papel == "concedente"), None)
    beneficiario_extraido = next((p for p in partes if p.papel == "beneficiario"), None)
    instrumento = prestacao.instrumento_principal
    plano = prestacao.planos.order_by("versao", "id").first()

    return {
        "concedente_cadastro": prestacao.concedente,
        "beneficiario_cadastro": prestacao.beneficiario,
        "concedente_extraido": concedente_extraido,
        "beneficiario_extraido": beneficiario_extraido,
        "termo": termo,
        "instrumento": instrumento,
        "plano": plano,
        "valor_global_plano": plano.valor_global if plano is not None else None,
        "valor_planejado": prestacao.valor_planejado,
        "valor_extracao_validada": prestacao.valor_extracao_validada,
        "situacao_termo": _situacao_termo(termo),
        "situacao_plano": _situacao_plano(plano),
        "situacao_termo_rotulo": rotulo_situacao(_situacao_termo(termo)),
        "situacao_plano_rotulo": rotulo_situacao(_situacao_plano(plano)),
    }


def _termo_da_prestacao(prestacao):
    from aplicacao.instrumentos.models import TermoFomento

    return (
        TermoFomento.objects.filter(documento__prestacao_contas=prestacao)
        .prefetch_related("partes", "campos")
        .order_by("-id")
        .first()
    )


def _situacao_termo(termo) -> str:
    if termo is None:
        return "sem_extracao"
    if getattr(termo, "congelado", False):
        return "congelado"
    if getattr(termo, "status", "") == "validado":
        return "validado"
    return "extraido_pendente"


def _situacao_plano(plano) -> str:
    if plano is None:
        return "sem_extracao"
    from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
    from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho

    total = ItemPlanoTrabalho.objects.filter(plano=plano).count()
    if total == 0:
        return "sem_itens"
    confirmados = ItemPlanoTrabalho.objects.filter(
        plano=plano,
        status_revisao__in=(StatusRevisaoPlano.CONFIRMADO, StatusRevisaoPlano.CORRIGIDO),
    ).count()
    if confirmados == 0:
        return "extraido_pendente"
    if confirmados == total:
        return "validado"
    return "parcialmente_validado"


def rotulo_situacao(codigo: str) -> str:
    return {
        "sem_extracao": "Sem extração disponível",
        "extraido_pendente": "Extração disponível · validação pendente",
        "parcialmente_validado": "Extração parcialmente validada",
        "validado": "Validado por conferência humana",
        "congelado": "Termo congelado",
        "sem_itens": "Plano sem itens extraídos",
    }.get(codigo, codigo)
