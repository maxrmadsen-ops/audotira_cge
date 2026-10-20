"""Helpers de apresentação do inventário e da conferência."""

from __future__ import annotations

from aplicacao.laboratorio.escolhas import EstadoClassificacao, EstadoRevisao
from aplicacao.laboratorio.models import InventarioPagina


def filtrar_paginas(lote, get) -> list[InventarioPagina]:
    consulta = lote.paginas.all()
    pagina = (get.get("pagina") or "").strip()
    if pagina.isdigit():
        consulta = consulta.filter(numero_fisico=int(pagina))
    tipo = (get.get("tipo") or "").strip()
    if tipo:
        consulta = consulta.filter(tipos_candidatos__contains=[tipo])
    classificacao = (get.get("classificacao") or "").strip()
    if classificacao == "sugerida":
        consulta = consulta.filter(estado_classificacao=EstadoClassificacao.PROPOSTO)
    elif classificacao == "confirmada":
        consulta = consulta.filter(
            estado_classificacao__in=(EstadoClassificacao.CONFIRMADO, EstadoClassificacao.CORRIGIDO)
        )
    elif classificacao == "inconclusiva":
        consulta = consulta.filter(estado_classificacao=EstadoClassificacao.INCONCLUSIVO)
    qualidade = (get.get("qualidade") or "").strip()
    if qualidade:
        consulta = consulta.filter(qualidade_extracao=qualidade)
    tecnica = (get.get("tecnica") or "").strip()
    if tecnica:
        consulta = consulta.filter(tecnica_utilizada=tecnica)
    revisao = (get.get("revisao") or "").strip()
    if revisao == "pendente":
        consulta = consulta.filter(estado_revisao=EstadoRevisao.PENDENTE)
    elif revisao == "concluida":
        consulta = consulta.filter(estado_revisao=EstadoRevisao.REVISADA)
    elif revisao == "ilegivel":
        consulta = consulta.filter(estado_revisao=EstadoRevisao.ILEGIVEL)
    return list(consulta.select_related("pagina_documento").prefetch_related("regioes"))


def resumo_pagina(pagina: InventarioPagina) -> str:
    regioes = [r for r in pagina.regioes.all() if r.tipo_documental != "outros_nao_classificados"]
    if not regioes and not pagina.tipos_candidatos:
        return "Sem classificação conclusiva"
    if not regioes:
        return "Candidatos sem peça segmentada: " + ", ".join(pagina.tipos_candidatos)
    from aplicacao.laboratorio.catalogo import rotulo_tipo

    return " · ".join(f"{rotulo_tipo(r.tipo_documental)}" for r in regioes)


def campos_uteis(regiao) -> list:
    """Remove campos genéricos vazios ou sem valor estruturado útil."""
    uteis = []
    for campo in regiao.campos.all():
        if campo.chave in {"titulo", "observacao"} and (
            not campo.valor_original or campo.valor_original.strip().isdigit() or len(campo.valor_original.strip()) < 3
        ):
            continue
        if not campo.valor_original and not campo.obrigatorio:
            continue
        uteis.append(campo)
    return uteis
