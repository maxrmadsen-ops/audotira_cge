"""Segunda leitura local de um recorte. Não escolhe um valor esperado."""

from __future__ import annotations

import re


_AUTH = re.compile(r"[0-9A-Za-z](?:\.\s?[0-9A-Za-z]{2,4}){3,8}")
_DATA = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
_DIGITO = re.compile(r"\b(\d{1,6})\b")


def _norm_auth(valor: str) -> str:
    return re.sub(r"\s+", "", valor or "").upper()


def decidir_autenticacao(original: str, leituras: list[str]) -> dict | None:
    extraidas = []
    for texto in leituras:
        achado = _AUTH.search(texto or "")
        if achado:
            extraidas.append(_norm_auth(achado.group(0)))
    unicas = set(extraidas)
    if len(extraidas) >= 2 and len(unicas) == 1:
        return {
            "valor": extraidas[0],
            "confianca": "evidencia_textual",
            "metodo": "ocr_recorte",
            "nota": "",
        }
    if len(unicas) > 1:
        return {
            "valor": original,
            "confianca": "ambiguo",
            "metodo": "ocr_regiao",
            "nota": "Leituras divergentes do código: " + " | ".join(extraidas),
        }
    return None


def decidir_matricula(leituras: list[str]) -> dict:
    extraidas = []
    for texto in leituras:
        achados = _DIGITO.findall(texto or "")
        if len(achados) == 1:
            extraidas.append(achados[0])
    if len(extraidas) >= 2 and len(set(extraidas)) == 1 and len(extraidas[0]) >= 2:
        return {
            "valor": extraidas[0],
            "confianca": "evidencia_textual",
            "metodo": "ocr_recorte",
            "nota": "",
        }
    nota = "Leituras do cadastro: " + (" | ".join(extraidas) if extraidas else "sem dígito isolado")
    return {"valor": "", "confianca": "ambiguo", "metodo": "ocr_regiao", "nota": nota}


def decidir_data(leituras: list[str]) -> dict | None:
    extraidas = []
    for texto in leituras:
        achados = _DATA.findall(texto or "")
        if len(achados) == 1:
            extraidas.append(achados[0])
    if len(extraidas) >= 2 and len(set(extraidas)) == 1:
        return {
            "valor": extraidas[0],
            "confianca": "evidencia_textual",
            "metodo": "ocr_recorte",
            "nota": "",
        }
    if any(re.search(r"recebi", texto or "", flags=re.IGNORECASE) for texto in leituras) or extraidas:
        return {
            "valor": "",
            "confianca": "ambiguo",
            "metodo": "ocr_regiao",
            "nota": "Data manuscrita sem acordo entre as leituras: " + " | ".join(extraidas or ["ilegível"]),
        }
    return None


def decidir_numero_impresso(leituras: list[str]) -> str:
    numeros = []
    for texto in leituras:
        limpo = (texto or "").strip()
        if not limpo or "/" in limpo or ":" in limpo:
            continue
        achados = re.findall(r"\b(\d{1,3})\b", limpo)
        if len(achados) == 1:
            numeros.append(achados[0])
    if len(numeros) >= 2 and len(set(numeros)) == 1:
        return numeros[0]
    return ""


def reler_faixa(imagem, caixa: dict, idioma: str) -> list[str]:
    import pytesseract
    from PIL import ImageOps

    largura, altura = imagem.size
    x0 = max(0, int(caixa["x"] * largura))
    y0 = max(0, int(caixa["y"] * altura))
    x1 = min(largura, int((caixa["x"] + caixa["largura"]) * largura))
    y1 = min(altura, int((caixa["y"] + caixa["altura"]) * altura))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return []
    recorte = imagem.crop((x0, y0, x1, y1)).convert("L")
    recorte = ImageOps.autocontrast(recorte.resize((recorte.width * 3, recorte.height * 3)))
    leituras = []
    for limiar in (False, True):
        alvo = recorte
        if limiar:
            alvo = recorte.point(lambda pixel: 255 if pixel > 170 else 0)
        try:
            leituras.append(pytesseract.image_to_string(alvo, lang=idioma, config="--psm 7") or "")
        except Exception:
            leituras.append("")
    return leituras


def aplicar_em_campos(campos: list[dict], chave: str, decisao: dict | None) -> None:
    if not decisao:
        return
    campo = next((item for item in campos if item["chave"] == chave), None)
    if campo is None:
        return
    nota = decisao.get("nota") or ""
    if nota:
        anterior = campo.get("trecho_evidencia") or ""
        campo["trecho_evidencia"] = (anterior + "\n" + nota).strip()
    if decisao["confianca"] == "evidencia_textual" and decisao.get("valor"):
        campo["valor_original"] = decisao["valor"]
        campo["valor_normalizado"] = decisao["valor"]
        campo["metodo"] = decisao["metodo"]
        campo["estado_confianca"] = decisao["confianca"]
    elif decisao["confianca"] == "ambiguo":
        campo["metodo"] = decisao["metodo"]
        campo["estado_confianca"] = "ambiguo"
        if chave in {"matricula", "data_recebimento"}:
            campo["valor_original"] = ""
            campo["valor_normalizado"] = ""
