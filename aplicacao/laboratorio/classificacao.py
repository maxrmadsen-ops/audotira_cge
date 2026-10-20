"""Classificação por página e região com heurísticas locais. Sem IA externa."""

from __future__ import annotations

import re
from decimal import Decimal

from aplicacao.laboratorio.catalogo import CATALOGO_TIPOS


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").lower()).strip()


def detectar_numero_impresso(texto: str) -> str:
    """Tenta ler numeração impressa sem confundir com página física do PDF."""
    padroes = (
        r"(?:fls?\.?|folha|página|pagina)\s*[:=]?\s*(\d{1,4})",
        r"(?:n[ºo°\.]*\s*da\s*página|pag\.?)\s*[:=]?\s*(\d{1,4})",
        r"\b(\d{1,4})\s*/\s*\d{2,4}\b",
    )
    for padrao in padroes:
        achado = re.search(padrao, texto or "", flags=re.IGNORECASE)
        if achado:
            return achado.group(1)
    return ""


def classificar_texto(texto: str) -> list[dict]:
    """
    Retorna candidatos tipados encontrados no texto.
    Não força categoria quando a evidência é insuficiente.
    """
    baixo = _normalizar(texto)
    if len(baixo) < 20:
        return []
    encontrados: list[dict] = []
    for item in CATALOGO_TIPOS:
        if item.codigo == "outros_nao_classificados":
            continue
        hits = [chave for chave in item.palavras_chave if chave in baixo]
        if not hits:
            continue
        confianca = min(Decimal("0.950"), Decimal("0.350") + Decimal("0.120") * len(hits))
        encontrados.append(
            {
                "tipo": item.codigo,
                "rotulo": item.rotulo,
                "hits": hits,
                "confianca": confianca,
                "metodo": "palavras_chave_locais",
            }
        )
    encontrados.sort(key=lambda item: item["confianca"], reverse=True)
    return encontrados


def segmentar_regioes(texto: str, candidatos: list[dict]) -> list[dict]:
    """
    Heurística de segmentação vertical quando há múltiplos tipos na mesma página.
    Coordenadas são relativas (0–1) à página.
    """
    if not candidatos:
        return [
            {
                "tipo": "outros_nao_classificados",
                "ordem": 1,
                "x": 0.0,
                "y": 0.0,
                "largura": 1.0,
                "altura": 1.0,
                "metodo_deteccao": "pagina_inteira_inconclusiva",
                "confianca": None,
            }
        ]
    unicos = []
    vistos = set()
    for item in candidatos:
        if item["tipo"] in vistos:
            continue
        vistos.add(item["tipo"])
        unicos.append(item)
    if len(unicos) == 1:
        item = unicos[0]
        return [
            {
                "tipo": item["tipo"],
                "ordem": 1,
                "x": 0.0,
                "y": 0.0,
                "largura": 1.0,
                "altura": 1.0,
                "metodo_deteccao": item["metodo"],
                "confianca": item["confianca"],
            }
        ]
    regioes = []
    altura = 1.0 / len(unicos)
    for indice, item in enumerate(unicos):
        regioes.append(
            {
                "tipo": item["tipo"],
                "ordem": indice + 1,
                "x": 0.0,
                "y": round(indice * altura, 4),
                "largura": 1.0,
                "altura": round(altura, 4),
                "metodo_deteccao": "segmentacao_heuristica_multipessa",
                "confianca": item["confianca"],
            }
        )
    return regioes
