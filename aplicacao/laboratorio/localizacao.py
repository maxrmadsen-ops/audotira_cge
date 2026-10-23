"""Caixas de evidência a partir das palavras do OCR. Sem coordenada inventada."""

from __future__ import annotations

import re


def _norm(texto: str) -> str:
    return re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", texto or "").upper()


def _casa(atual: str, alvo: str) -> bool:
    if not atual:
        return False
    return atual == alvo or alvo in atual or (atual in alvo and len(atual) >= 3)


def caixa_da_rubrica(palavras: list[dict], codigo: str, valor: str = "") -> dict | None:
    """Ancora a rubrica no código. O valor zero pode repetir; o código não."""
    codigo_n = _norm(codigo)
    if not codigo_n:
        return None
    normas = [_norm(palavra.get("texto", "")) for palavra in palavras]
    indices = [indice for indice, norma in enumerate(normas) if norma == codigo_n]
    if len(indices) != 1:
        return None
    inicio = indices[0]
    y = float(palavras[inicio]["y"])
    x = float(palavras[inicio]["x"])
    alvo_valor = _norm(valor)
    fim = inicio
    for posicao in range(inicio + 1, min(inicio + 16, len(palavras))):
        if abs(float(palavras[posicao]["y"]) - y) > 0.025:
            continue
        if float(palavras[posicao]["x"]) + float(palavras[posicao]["largura"]) < x:
            continue
        token = normas[posicao]
        bruto = (palavras[posicao].get("texto") or "").strip()
        if re.fullmatch(r"\d{2,3}(?:\.\d)?", bruto) and token != codigo_n:
            break
        fim = posicao
        if alvo_valor and alvo_valor in token:
            break
    return _unir(palavras[inicio : fim + 1])


def caixa_do_valor(palavras: list[dict], consulta: str) -> dict | None:
    """Devolve uma caixa só quando a consulta aparece uma única vez."""
    tokens = [_norm(parte) for parte in re.split(r"\s+", (consulta or "").strip())]
    alvos = [token for token in tokens if len(token) >= 2]
    if not alvos or len((consulta or "").strip()) > 160:
        return None
    normas = [_norm(palavra.get("texto", "")) for palavra in palavras]
    encontrados = []
    for inicio, inicial in enumerate(normas):
        if not _casa(inicial, alvos[0]):
            continue
        cursor = 1
        fim = inicio
        posicao = inicio + 1
        while posicao < len(palavras) and cursor < len(alvos) and posicao < inicio + 14:
            atual = normas[posicao]
            if not atual:
                posicao += 1
                continue
            if not _casa(atual, alvos[cursor]):
                break
            fim = posicao
            cursor += 1
            posicao += 1
        if cursor == len(alvos):
            encontrados.append((inicio, fim))
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


def caixa_na_linha(palavras: list[dict], valor: str, ancora: str) -> dict | None:
    """Localiza o valor na mesma linha de uma âncora única. Não devolve a linha inteira."""
    ancora_n = _norm(ancora)
    valor_n = _norm(valor)
    if not ancora_n or not valor_n or ancora_n == valor_n:
        return None
    normas = [_norm(palavra.get("texto", "")) for palavra in palavras]
    indices = [indice for indice, norma in enumerate(normas) if norma == ancora_n]
    if len(indices) != 1:
        return None
    y = float(palavras[indices[0]]["y"])
    hits = [
        indice
        for indice, norma in enumerate(normas)
        if abs(float(palavras[indice]["y"]) - y) <= 0.02 and (norma == valor_n or (len(valor_n) >= 4 and valor_n in norma))
    ]
    if len(hits) != 1:
        return None
    return _unir([palavras[hits[0]]])


def localizar_campos(campos: list[dict], palavras: list[dict], regiao: dict) -> list[dict]:
    for campo in campos:
        consulta = campo.get("valor_original") or ""
        caixa = caixa_do_valor(palavras, consulta)
        trecho = campo.get("trecho_evidencia") or ""
        if caixa is None and trecho and trecho != consulta and len(trecho) <= len(consulta) + 12:
            caixa = caixa_do_valor(palavras, trecho)
        elif caixa is None and trecho and consulta:
            melhor = None
            for parte in re.split(r"\s+", trecho):
                if not parte or _norm(parte) == _norm(consulta):
                    continue
                if caixa_do_valor(palavras, parte) is None:
                    continue
                candidata = caixa_na_linha(palavras, consulta, parte)
                if candidata is not None and (melhor is None or len(_norm(parte)) > melhor[0]):
                    melhor = (len(_norm(parte)), candidata)
            if melhor is not None:
                caixa = melhor[1]
        if caixa is None and not consulta and "local e data" in trecho.lower():
            caixa = caixa_do_valor(palavras, "LOCAL E DATA")
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
