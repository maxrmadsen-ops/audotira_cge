"""Sugestões de vínculo entre evidências. Coincidência de valor não confirma sozinha."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aplicacao.laboratorio.models import CampoExtraido, RegiaoDocumental, VinculoEvidencia
from aplicacao.laboratorio.escolhas import EstadoVinculo


def _decimal(texto: str) -> Decimal | None:
    limpo = (texto or "").strip()
    if not limpo:
        return None
    try:
        return Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None


def _campo(regiao: RegiaoDocumental, chave: str) -> str:
    item = regiao.campos.filter(chave=chave).exclude(valor_normalizado="").first()
    if item:
        return item.valor_normalizado or item.valor_original
    item = regiao.campos.filter(chave=chave).exclude(valor_original="").first()
    return item.valor_original if item else ""


def sugerir_vinculos(lote) -> list[VinculoEvidencia]:
    regioes = list(
        RegiaoDocumental.objects.filter(lote=lote).select_related("pagina").prefetch_related("campos")
    )
    por_tipo: dict[str, list[RegiaoDocumental]] = {}
    for regiao in regioes:
        por_tipo.setdefault(regiao.tipo_documental, []).append(regiao)

    criados: list[VinculoEvidencia] = []
    criados.extend(_pares_holerite_transferencia(lote, por_tipo))
    criados.extend(_pares_rescisao_quitacao(lote, por_tipo))
    criados.extend(_pares_fgts(lote, por_tipo))
    criados.extend(_pares_dispensa(lote, por_tipo))
    return criados


def _criar(lote, origem, destino, tipo, criterios, divergencias) -> VinculoEvidencia:
    return VinculoEvidencia.objects.create(
        lote=lote,
        origem=origem,
        destino=destino,
        tipo_vinculo=tipo,
        criterios=criterios,
        divergencias=divergencias,
        estado=EstadoVinculo.SUGERIDO,
    )


def _pares_holerite_transferencia(lote, por_tipo) -> list[VinculoEvidencia]:
    resultado = []
    for holerite in por_tipo.get("holerite", []):
        liquido = _decimal(_campo(holerite, "valor_liquido"))
        funcionario = (_campo(holerite, "funcionario") or "").lower()
        for transferencia in por_tipo.get("comprovante_transferencia", []):
            valor = _decimal(_campo(transferencia, "valor"))
            beneficiario = (_campo(transferencia, "beneficiario") or "").lower()
            criterios = []
            divergencias = []
            if liquido is not None and valor is not None and liquido == valor:
                criterios.append("mesmo_valor_liquido")
            elif liquido is not None and valor is not None:
                divergencias.append(f"valores_distintos:{liquido}!={valor}")
            if funcionario and beneficiario and (funcionario in beneficiario or beneficiario in funcionario):
                criterios.append("nome_beneficiario_aproximado")
            if holerite.pagina_id == transferencia.pagina_id:
                criterios.append("mesma_pagina_fisica")
            if criterios:
                resultado.append(
                    _criar(
                        lote,
                        holerite,
                        transferencia,
                        "holerite_transferencia",
                        criterios,
                        divergencias,
                    )
                )
    return resultado


def _pares_rescisao_quitacao(lote, por_tipo) -> list[VinculoEvidencia]:
    resultado = []
    for rescisao in por_tipo.get("termo_rescisao", []):
        trabalhador = (_campo(rescisao, "trabalhador") or "").lower()
        for quitacao in por_tipo.get("termo_quitacao", []):
            nome = (_campo(quitacao, "trabalhador") or "").lower()
            criterios = []
            if trabalhador and nome and (trabalhador in nome or nome in trabalhador):
                criterios.append("mesmo_trabalhador")
            if abs(rescisao.pagina.numero_fisico - quitacao.pagina.numero_fisico) <= 3:
                criterios.append("proximidade_paginas")
            if criterios:
                resultado.append(
                    _criar(lote, rescisao, quitacao, "rescisao_quitacao", criterios, [])
                )
        for transferencia in por_tipo.get("comprovante_transferencia", []):
            beneficiario = (_campo(transferencia, "beneficiario") or "").lower()
            criterios = []
            if trabalhador and beneficiario and (trabalhador in beneficiario or beneficiario in trabalhador):
                criterios.append("mesmo_trabalhador_beneficiario")
            if criterios:
                resultado.append(
                    _criar(lote, rescisao, transferencia, "rescisao_pagamento", criterios, [])
                )
    return resultado


def _pares_fgts(lote, por_tipo) -> list[VinculoEvidencia]:
    resultado = []
    for guia in por_tipo.get("guia_fgts", []):
        competencia = _campo(guia, "competencia")
        valor = _decimal(_campo(guia, "valor_recolhimento"))
        for comprovante in por_tipo.get("comprovante_fgts", []):
            criterios = []
            divergencias = []
            if competencia and competencia == _campo(comprovante, "competencia"):
                criterios.append("mesma_competencia")
            valor_comp = _decimal(_campo(comprovante, "valor_recolhimento"))
            if valor is not None and valor_comp is not None and valor == valor_comp:
                criterios.append("mesmo_valor")
            elif valor is not None and valor_comp is not None:
                divergencias.append(f"valores_distintos:{valor}!={valor_comp}")
            if abs(guia.pagina.numero_fisico - comprovante.pagina.numero_fisico) <= 2:
                criterios.append("proximidade_paginas")
            if criterios:
                resultado.append(
                    _criar(lote, guia, comprovante, "guia_fgts_comprovante", criterios, divergencias)
                )
    return resultado


def _pares_dispensa(lote, por_tipo) -> list[VinculoEvidencia]:
    resultado = []
    for dispensa in por_tipo.get("comunicacao_dispensa", []):
        trabalhador = (_campo(dispensa, "trabalhador") or "").lower()
        for rescisao in por_tipo.get("termo_rescisao", []):
            nome = (_campo(rescisao, "trabalhador") or "").lower()
            criterios = []
            if trabalhador and nome and (trabalhador in nome or nome in trabalhador):
                criterios.append("mesmo_trabalhador")
            if criterios:
                resultado.append(
                    _criar(lote, dispensa, rescisao, "dispensa_rescisao", criterios, [])
                )
    return resultado
