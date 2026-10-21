"""Caixas de evidência a partir das palavras do OCR. Sem coordenada inventada."""

from __future__ import annotations

import re


def _norm(texto: str) -> str:
    return re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", texto or "").upper()


def caixa_do_valor(palavras: list[dict], consulta: str) -> dict | None:
    """Devolve uma caixa só quando a consulta aparece uma única vez."""
    tokens = [_norm(parte) for parte in re.split(r"\s+", (consulta or "").strip())]
    alvos = [token for token in tokens if len(token) >= 2]
    if not alvos or len((consulta or "").strip()) > 160:
        return None
    normas = [_norm(palavra.get("texto", "")) for palavra in palavras]
    encontrados = []
    for inicio in range(len(palavras)):
        cursor = 0
        fim = inicio
        while fim < len(palavras) and cursor < len(alvos) and fim < inicio + 14:
            atual = normas[fim]
            if atual and (atual == alvos[cursor] or alvos[cursor] in atual or (atual in alvos[cursor] and len(atual) >= 3)):
                cursor += 1
                if cursor == len(alvos):
                    encontrados.append((inicio, fim))
                    break
            fim += 1
    if len(encontrados) != 1:
        return None
    inicio, fim = encontrados[0]
    return _unir(palavras[inicio : fim + 1])


def faixa_do_rotulo(palavras: list[dict], padrao: str, altura: float = 0.05) -> dict | None:
    hits = [palavra for palavra in palavras if re.search(padrao, palavra.get("texto", ""), flags=re.IGNORECASE)]
    if len(hits) != 1:
        return None
    palavra = hits[0]
    y = max(0.0, float(palavra["y"]) - 0.004)
    return {"x": 0.0, "y": y, "largura": 1.0, "altura": min(altura, 1 - y)}


def faixa_abaixo(palavras: list[dict], padrao: str) -> dict | None:
    hits = [palavra for palavra in palavras if re.search(padrao, palavra.get("texto", ""), flags=re.IGNORECASE)]
    if len(hits) != 1:
        return None
    palavra = hits[0]
    y = min(0.96, float(palavra["y"]) + float(palavra["altura"]))
    return {"x": 0.0, "y": y, "largura": 0.28, "altura": min(0.055, 1 - y)}


def projetar_pagina(caixa: dict, regiao: dict) -> dict:
    return {
        "evidencia_x": round(regiao["x"] + caixa["x"] * regiao["largura"], 4),
        "evidencia_y": round(regiao["y"] + caixa["y"] * regiao["altura"], 4),
        "evidencia_largura": round(caixa["largura"] * regiao["largura"], 4),
        "evidencia_altura": round(max(caixa["altura"] * regiao["altura"], 0.012), 4),
    }


def localizar_campos(campos: list[dict], palavras: list[dict], regiao: dict) -> list[dict]:
    for campo in campos:
        consulta = campo.get("valor_original") or ""
        caixa = caixa_do_valor(palavras, consulta)
        trecho = campo.get("trecho_evidencia") or ""
        if caixa is None and trecho and trecho != consulta and len(trecho) <= 160:
            caixa = caixa_do_valor(palavras, trecho)
        if caixa is None:
            campo["localizacao_precisa"] = False
            continue
        campo.update(projetar_pagina(caixa, regiao))
        campo["localizacao_precisa"] = True
    return campos


def _unir(palavras: list[dict]) -> dict:
    x0 = min(float(palavra["x"]) for palavra in palavras)
    y0 = min(float(palavra["y"]) for palavra in palavras)
    x1 = max(float(palavra["x"]) + float(palavra["largura"]) for palavra in palavras)
    y1 = max(float(palavra["y"]) + float(palavra["altura"]) for palavra in palavras)
    return {"x": x0, "y": y0, "largura": max(x1 - x0, 0.01), "altura": max(y1 - y0, 0.008)}
