"""Fonte citada precisa existir no contexto enviado. Fonte nova é rejeitada."""


def _chave(tipo: str, identificador: str, pagina) -> tuple:
    return (str(tipo or ""), str(identificador or ""), None if pagina in (None, "") else str(pagina))


def catalogo_de_fontes(contexto: dict) -> set[tuple]:
    catalogo = set()
    for item in contexto.get("itens") or []:
        catalogo.add(_chave(item.get("tipo"), item.get("identificador"), item.get("pagina")))
        catalogo.add(_chave(item.get("tipo"), item.get("identificador"), None))
    return catalogo


def validar_fontes(contexto: dict, resposta: dict) -> tuple[list, list, list, list]:
    catalogo = catalogo_de_fontes(contexto)
    fontes_ok = []
    fontes_rejeitadas = []
    for fonte in resposta.get("fontes_utilizadas") or []:
        if not isinstance(fonte, dict):
            fontes_rejeitadas.append({"motivo": "formato"})
            continue
        chave = _chave(fonte.get("tipo"), fonte.get("identificador"), fonte.get("pagina"))
        if chave in catalogo or _chave(fonte.get("tipo"), fonte.get("identificador"), None) in catalogo:
            fontes_ok.append(fonte)
        else:
            fontes_rejeitadas.append(fonte)
    fundamentos_ok = []
    fundamentos_rejeitados = []
    for fundamento in resposta.get("fundamentos_normativos") or []:
        if not isinstance(fundamento, dict):
            fundamentos_rejeitados.append({"motivo": "formato"})
            continue
        chave = _chave("norma", fundamento.get("identificador"), fundamento.get("artigo") or fundamento.get("pagina"))
        simples = _chave("norma", fundamento.get("identificador"), None)
        if chave in catalogo or simples in catalogo:
            fundamentos_ok.append(fundamento)
        else:
            fundamentos_rejeitados.append(fundamento)
    return fontes_ok, fontes_rejeitadas, fundamentos_ok, fundamentos_rejeitados
