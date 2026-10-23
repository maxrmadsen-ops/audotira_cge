"""Inspeção pontual de páginas sem OCR e correção de menções administrativas.

Abrir a Conferência Integrada não chama estas rotinas.
"""

from __future__ import annotations

import re

from django.db.models import Q

from aplicacao.documentos.armazenamento import ler_arquivo
from aplicacao.documentos.qualidade import avaliar_qualidade
from aplicacao.laboratorio.classificacao import (
    candidatos_da_peca,
    classificar_texto,
    mencao_administrativa,
    tipo_principal,
)
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoRevisao
from aplicacao.laboratorio.models import CadeiaConciliacao, RegiaoDocumental, RevisaoLaboratorio, VinculoEvidencia

PAGINAS_HOMOLOGADAS = frozenset({17, 91, 92, 93})
LIMITE_AMOSTRA = 12
AMOSTRAS = (
    (8, "Página anterior ao termo que cita o balancete atualizado."),
    (7, "Mesma sequência visual, imediatamente antes desse termo."),
    (6, "Mesma sequência visual, no início do trecho sem texto."),
    (16, "Adjacente ao holerite da página 17, sem reprocessar a página homologada."),
    (18, "Adjacente ao holerite da página 17, sem reprocessar a página homologada."),
    (50, "Ponto intermediário das páginas que só têm o número impresso."),
    (110, "Adjacente à guia da página 111, sem reprocessar essa guia."),
    (112, "Adjacente à guia da página 111, sem reprocessar essa guia."),
    (115, "Adjacente à guia da página 116, sem reprocessar essa guia."),
    (117, "Adjacente à guia da página 116, sem reprocessar essa guia."),
)
_TIPOS_MENCAO = {"balancete", "folha_pagamento", "extrato_bancario", "oficio_encaminhamento"}
_MOEDA = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
_SINAIS = ("receita", "despesa", "saldo", "competência", "competencia", "líquido", "liquido", "fgts", "holerite")


class ErroDescoberta(Exception):
    """A amostra pedida sai do limite deste ciclo."""


def corrigir_mencoes(lote, usuario=None) -> list[dict]:
    """Troca o tipo de uma menção já gravada e conserva campos, texto e revisão humana."""
    alteracoes = []
    regioes = (
        RegiaoDocumental.objects.filter(lote=lote, tipo_documental__in=_TIPOS_MENCAO)
        .select_related("pagina__pagina_documento")
        .order_by("pagina__numero_fisico", "ordem", "id")
    )
    for regiao in regioes:
        pagina = regiao.pagina
        if pagina.numero_fisico in PAGINAS_HOMOLOGADAS:
            alteracoes.append({"peca_id": regiao.pk, "situacao": "preservada", "motivo": "página homologada"})
            continue
        texto = ""
        if pagina.pagina_documento_id:
            texto = pagina.pagina_documento.texto_extraido or ""
        if not texto:
            texto = regiao.texto_regiao or ""
        if not _tipo_so_mencionado(texto, regiao.tipo_documental):
            continue
        bloqueio = _bloqueio(regiao)
        if bloqueio:
            alteracoes.append({"peca_id": regiao.pk, "situacao": "preservada", "motivo": bloqueio})
            continue
        anterior = regiao.tipo_documental
        novo = _tipo_substituto(texto)
        regiao.tipo_documental = novo
        regiao.justificativa = (
            f"Classificação anterior: {anterior}. "
            "O nome aparece como menção ou anexo. Campos e texto originais preservados."
        )
        regiao.save(update_fields=["tipo_documental", "justificativa", "atualizado_em"])
        RevisaoLaboratorio.objects.create(
            lote=lote,
            alvo="regiao",
            alvo_id=regiao.pk,
            acao="reclassificar_mencao",
            justificativa=regiao.justificativa,
            detalhe={
                "tipo_anterior": anterior,
                "tipo_novo": novo,
                "pagina": pagina.numero_fisico,
            },
            responsavel=usuario,
        )
        alteracoes.append({"peca_id": regiao.pk, "situacao": "reclassificada", "de": anterior, "para": novo})
    return alteracoes


def inspecionar_paginas(lote, numeros, extrator) -> list[dict]:
    """OCR local só nas páginas pedidas. Não cria peça, cadeia nem pagamento."""
    pedidos = tuple(numeros)
    if len(pedidos) > LIMITE_AMOSTRA:
        raise ErroDescoberta("A amostra passa do limite de páginas deste ciclo.")
    bloqueadas = sorted(set(pedidos) & PAGINAS_HOMOLOGADAS)
    if bloqueadas:
        raise ErroDescoberta(f"Páginas homologadas fora da descoberta: {bloqueadas}.")
    justificativas = dict(AMOSTRAS)
    caminho = ler_arquivo(lote.documento.nome_armazenado)
    registros = []
    for numero in pedidos:
        inventario = lote.paginas.select_related("pagina_documento").get(numero_fisico=numero)
        existente = RevisaoLaboratorio.objects.filter(
            lote=lote,
            alvo="descoberta_pagina",
            alvo_id=numero,
            acao="inspecao_ocr",
        ).first()
        if existente is not None:
            registros.append(existente.detalhe)
            continue
        nativo = ""
        if inventario.pagina_documento_id:
            nativo = inventario.pagina_documento.texto_extraido or ""
        texto_ocr, _caixas = extrator.extrair_pagina(caminho, numero)
        detalhe = _detalhe(numero, justificativas.get(numero, "Página incluída na amostra autorizada."), nativo, texto_ocr or "")
        RevisaoLaboratorio.objects.create(
            lote=lote,
            alvo="descoberta_pagina",
            alvo_id=numero,
            acao="inspecao_ocr",
            justificativa=detalhe["justificativa_amostra"],
            detalhe=detalhe,
        )
        registros.append(detalhe)
    return registros


def ler_descobertas(lote) -> list[dict]:
    revisoes = RevisaoLaboratorio.objects.filter(lote=lote, alvo="descoberta_pagina", acao="inspecao_ocr").order_by("alvo_id")
    return [revisao.detalhe for revisao in revisoes]


def _tipo_so_mencionado(texto: str, tipo: str) -> bool:
    if not mencao_administrativa(texto):
        return False
    brutos = {item["tipo"] for item in classificar_texto(texto)}
    filtrados = {item["tipo"] for item in candidatos_da_peca(classificar_texto(texto), texto)}
    return tipo in brutos and tipo not in filtrados


def _tipo_substituto(texto: str) -> str:
    baixo = texto.lower()
    if "termo de desentranhamento" in baixo or "foram desentranhadas" in baixo:
        return "administrativo_sgpe"
    return "outros_nao_classificados"


def _bloqueio(regiao) -> str:
    if regiao.estado_revisao != EstadoRevisao.PENDENTE:
        return "revisão da peça já registrada"
    if regiao.campos.exclude(estado_revisao__in=[EstadoCampo.PENDENTE, EstadoCampo.AUSENTE]).exists():
        return "campo com revisão humana"
    if CadeiaConciliacao.objects.filter(Q(execucao=regiao) | Q(apoio=regiao) | Q(comprovante=regiao)).exists():
        return "peça presente em cadeia"
    if VinculoEvidencia.objects.filter(Q(origem=regiao) | Q(destino=regiao)).exists():
        return "peça presente em vínculo"
    return ""


def _detalhe(numero: int, justificativa: str, nativo: str, texto_ocr: str) -> dict:
    qualidade, _necessita = avaliar_qualidade(texto_ocr)
    candidatos = candidatos_da_peca(classificar_texto(texto_ocr), texto_ocr)
    principal = tipo_principal(candidatos, texto_ocr) if candidatos else None
    baixo = texto_ocr.lower()
    sinais = [sinal for sinal in _SINAIS if sinal in baixo]
    moedas = _MOEDA.findall(texto_ocr)[:8]
    return {
        "numero": numero,
        "justificativa_amostra": justificativa,
        "qualidade_visual": _qualidade_legivel(qualidade),
        "texto_nativo": (nativo or "")[:500],
        "caracteres_nativos": len(nativo or ""),
        "texto_ocr": (texto_ocr or "")[:1500],
        "caracteres_ocr": len(texto_ocr or ""),
        "tipo": principal["tipo"] if principal else "nao_identificado",
        "confianca": str(principal["confianca"]) if principal else "0",
        "campos_financeiros": sinais + moedas,
        "revisao_humana": True,
        "altera_totais": False,
    }


def _qualidade_legivel(qualidade: str) -> str:
    return {
        "suficiente": "legível",
        "insuficiente": "texto insuficiente",
        "ausente": "sem texto",
        "ilegivel": "leitura fraca",
    }.get(qualidade, qualidade or "não avaliada")
