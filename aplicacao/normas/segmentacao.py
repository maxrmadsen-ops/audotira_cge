import re

_ARTIGO = re.compile(r"(?i)^art(?:igo)?\.?\s*(\d+)\s*[º°o.]?\s*[-–.]?\s*(.*)$")
_PARAGRAFO = re.compile(r"(?i)^(?:§|par[aá]grafo)\s*(único|unico|\d+)?\s*[-–.]?\s*(.*)$")
_INCISO = re.compile(r"(?i)^(?:inciso\s+)?([IVXLCDM]{1,8})\s*[-–—.]\s*(.*)$")
_ALINEA = re.compile(r"(?i)^([a-z])\)\s+(.*)$")
_ESTRUTURA = re.compile(r"(?i)^(t[ií]tulo|cap[ií]tulo|se[cç][aã]o)\s+(\S+)\s*[-–.]?\s*(.*)$")


def segmentar(paginas: list[dict]) -> list[dict]:
    """Identifica dispositivos quando o texto os declara. Não completa lacunas."""
    linhas = _linhas(paginas)
    if not any(_ARTIGO.match(item["linha"]) for item in linhas):
        return [_sem_estrutura(paginas)]
    blocos: list[dict] = []
    atual: dict | None = None
    titulo = capitulo = secao = ""
    for item in linhas:
        linha = item["linha"]
        pagina = item["pagina"]
        estrutura = _ESTRUTURA.match(linha)
        if estrutura:
            nivel, numero, resto = estrutura.group(1).lower(), estrutura.group(2), estrutura.group(3).strip()
            rotulo = f"{nivel} {numero}".strip()
            if nivel.startswith("t"):
                titulo = resto or rotulo
            elif nivel.startswith("c"):
                capitulo = resto or rotulo
            else:
                secao = resto or rotulo
            if atual is not None:
                atual["linhas"].append(linha)
                atual["pagina_fim"] = pagina
            continue
        artigo = _ARTIGO.match(linha)
        if artigo:
            if atual is not None:
                blocos.append(atual)
            atual = _bloco(artigo.group(1), artigo.group(2), pagina, titulo, capitulo, secao)
            continue
        if atual is None:
            continue
        atual["pagina_fim"] = pagina
        paragrafo = _PARAGRAFO.match(linha)
        inciso = _INCISO.match(linha)
        alinea = _ALINEA.match(linha)
        if paragrafo:
            atual["paragrafo"] = (paragrafo.group(1) or "único").lower().replace("unico", "único")
        elif inciso and not _ARTIGO.match(linha):
            atual["inciso"] = inciso.group(1).upper()
        elif alinea:
            atual["alinea"] = alinea.group(1).lower()
        atual["linhas"].append(linha)
    if atual is not None:
        blocos.append(atual)
    return blocos


def _linhas(paginas: list[dict]) -> list[dict]:
    resultado = []
    for pagina in paginas:
        numero = pagina.get("numero_pagina") or 1
        for bruta in (pagina.get("texto_extraido") or "").splitlines():
            linha = bruta.strip()
            if linha:
                resultado.append({"pagina": numero, "linha": linha})
    return resultado


def _bloco(artigo: str, primeira: str, pagina: int, titulo: str, capitulo: str, secao: str) -> dict:
    linhas = [f"Art. {artigo} {primeira}".strip()]
    return {
        "artigo": artigo,
        "paragrafo": "",
        "inciso": "",
        "alinea": "",
        "secao": secao,
        "titulo_secao": titulo or capitulo or secao,
        "pagina_inicio": pagina,
        "pagina_fim": pagina,
        "linhas": linhas,
        "metadados": {"titulo": titulo, "capitulo": capitulo, "secao": secao},
        "estruturado": True,
    }


def _sem_estrutura(paginas: list[dict]) -> dict:
    numeros = [pagina.get("numero_pagina") or 1 for pagina in paginas]
    texto = "\n".join((pagina.get("texto_extraido") or "").strip() for pagina in paginas).strip()
    return {
        "artigo": "",
        "paragrafo": "",
        "inciso": "",
        "alinea": "",
        "secao": "",
        "titulo_secao": "",
        "pagina_inicio": min(numeros) if numeros else None,
        "pagina_fim": max(numeros) if numeros else None,
        "linhas": [texto] if texto else [],
        "metadados": {},
        "estruturado": False,
    }
