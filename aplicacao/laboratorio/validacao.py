"""Validação semântica de datas, protocolos e rótulos. Sem regra por página ou pessoa."""

from __future__ import annotations

import re
from datetime import date


_DATA = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")
_ROTULOS_TRCT = (
    ("data_admissao", re.compile(r"(?:\d{1,2}\s+)?data de admiss[aã]o", re.IGNORECASE)),
    ("data_aviso", re.compile(r"(?:\d{1,2}\s+)?data do aviso(?:\s+pr[eé]vio)?", re.IGNORECASE)),
    ("data_desligamento", re.compile(r"(?:\d{1,2}\s+)?data de afastamento|(?:\d{1,2}\s+)?data de desligamento", re.IGNORECASE)),
)


def normalizar_data(token: str) -> str:
    """Devolve DD/MM/AAAA só quando dia, mês e ano formam uma data real."""
    achado = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*", token or "")
    if not achado:
        return ""
    dia, mes, ano = int(achado.group(1)), int(achado.group(2)), int(achado.group(3))
    if ano < 100:
        ano += 2000 if ano < 70 else 1900
    if not 1900 <= ano <= 2100:
        return ""
    try:
        return date(ano, mes, dia).strftime("%d/%m/%Y")
    except ValueError:
        return ""


def data_valida_no_texto(texto: str) -> str:
    for token in _DATA.findall(texto or ""):
        normal = normalizar_data(token)
        if normal:
            return normal
    return ""


def data_rejeitada_no_texto(texto: str) -> str:
    for token in _DATA.findall(texto or ""):
        if not normalizar_data(token):
            return token
    return ""


def datas_rotuladas_trct(texto: str) -> dict[str, str]:
    """Associa cada rótulo à sua data. Aviso prévio não preenche o afastamento."""
    encontrados = []
    for chave, padrao in _ROTULOS_TRCT:
        achado = padrao.search(texto or "")
        if achado:
            encontrados.append((chave, achado.group(0), achado.start(), achado.end()))
    encontrados.sort(key=lambda item: item[2])
    if not encontrados:
        return {}
    inicio = encontrados[0][2]
    fim = min(len(texto), encontrados[-1][3] + 180)
    datas = []
    for achado in _DATA.finditer(texto[inicio:fim]):
        normal = normalizar_data(achado.group(0))
        if normal:
            datas.append((inicio + achado.start(), normal))
    resultado = {}
    for indice, (chave, rotulo, _inicio, fim_rotulo) in enumerate(encontrados):
        if indice + 1 < len(encontrados):
            proximo = encontrados[indice + 1][2]
        else:
            quebra = (texto or "").find("\n", fim_rotulo)
            proximo = quebra if quebra != -1 else fim_rotulo + 16
        entre = [valor for posicao, valor in datas if fim_rotulo <= posicao < proximo]
        if len(entre) == 1:
            resultado[chave] = entre[0]
            resultado[f"{chave}__evidencia"] = f"{rotulo.strip()} {entre[0]}"
    if len([chave for chave, *_resto in encontrados if chave in resultado]) == len(encontrados):
        return resultado
    if resultado:
        return resultado
    posteriores = [valor for posicao, valor in datas if posicao >= encontrados[-1][3]]
    if len(posteriores) < len(encontrados):
        return {}
    for (chave, rotulo, _inicio, _fim), valor in zip(encontrados, posteriores):
        resultado[chave] = valor
        resultado[f"{chave}__evidencia"] = f"{rotulo.strip()} {valor}"
    return resultado


def protocolo_documental(texto: str) -> str:
    achado = re.search(
        r"(?:protocolo|comunica[cç][aã]o de dispensa)\s*[-–:]*\s*(\d{6,})",
        texto or "",
        flags=re.IGNORECASE,
    )
    return achado.group(1) if achado else ""


def motivo_rotulado(texto: str) -> str:
    """Motivo só com rótulo próprio. Número de protocolo não é motivo."""
    achado = re.search(r"\bmotivo\s*[:\-]\s*([^\n]{3,80})", texto or "", flags=re.IGNORECASE)
    if not achado:
        return ""
    valor = achado.group(1).strip(" :-")
    if re.fullmatch(r"[\d.\-/]+", valor):
        return ""
    return valor
