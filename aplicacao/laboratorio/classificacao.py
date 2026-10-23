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


def tipo_principal(candidatos: list[dict], texto: str) -> dict | None:
    """Prefere a guia quando o texto é recolhimento de FGTS, não transferência salarial."""
    if not candidatos:
        return None
    baixo = _normalizar(texto)
    if "comprovante de pagamento de darf" in baixo or "darf/darf" in baixo or "convenio rfb-darf" in baixo or "convênio rfb-darf" in baixo:
        darf_pago = next((item for item in candidatos if item["tipo"] == "comprovante_darf"), None)
        if darf_pago is not None:
            return darf_pago
    if "documento de arrecada" in baixo or "receitas federais" in baixo:
        guia = next((item for item in candidatos if item["tipo"] == "darf"), None)
        if guia is not None:
            return guia
    if "total de proventos" in baixo or "demonstrativo de pagamento" in baixo or "holerite" in baixo:
        holerite = next((item for item in candidatos if item["tipo"] == "holerite"), None)
        if holerite is not None:
            return holerite
    if "comprovante de transferencia" in baixo or "comprovante de transferência" in baixo or "transferido para" in baixo:
        transferencia = next((item for item in candidatos if item["tipo"] == "comprovante_transferencia"), None)
        if transferencia is not None:
            return transferencia
    recolhimento = ("fgts" in baixo or "grf" in baixo) and (
        "comprovante de pagamento" in baixo or "valor deposito" in baixo or "valor depósito" in baixo or "guia de recolhimento" in baixo
    )
    if "termo de quitação" in baixo or "termo de quitacao" in baixo:
        titulo_trct = (
            "termo de rescisão do contrato de trabalho" in baixo
            or "termo de rescisao do contrato de trabalho" in baixo
        )
        if not titulo_trct:
            quitacao = next((item for item in candidatos if item["tipo"] == "termo_quitacao"), None)
            if quitacao is not None:
                return quitacao
    if not recolhimento:
        return candidatos[0]
    for codigo in ("guia_fgts", "comprovante_fgts"):
        achado = next((item for item in candidatos if item["tipo"] == codigo), None)
        if achado is not None:
            return achado
    return candidatos[0]


def mencao_administrativa(texto: str) -> bool:
    """E-mail ou termo que cita um anexo não é o documento financeiro citado."""
    baixo = _normalizar(texto)
    if "termo de desentranhamento" in baixo or "foram desentranhadas" in baixo:
        return True
    if "gmail.com" in baixo or "e-mail de" in baixo:
        return True
    return bool(re.search(r"\d+\s+anexos?\b", baixo) and ".pdf" in baixo)


def _oficio_so_no_nome_de_arquivo(texto: str) -> bool:
    baixo = _normalizar(texto)
    sem_arquivo = re.sub(r"of[ií]cios?\b.{0,40}?\.pdf", " ", baixo, flags=re.IGNORECASE)
    return re.search(r"of[ií]cio", sem_arquivo, flags=re.IGNORECASE) is None


def candidatos_da_peca(candidatos: list[dict], texto: str) -> list[dict]:
    """Citação em formulário ou em lista de anexos não vira outro documento."""
    baixo = _normalizar(texto)
    formulario = any(
        titulo in baixo
        for titulo in ("termo de rescisão", "termo de rescisao", "termo de quitação", "termo de quitacao")
    )
    dispensa_propria = "comunicação de dispensa" in baixo or "comunicacao de dispensa" in baixo
    titulo_trct = (
        "termo de rescisão do contrato de trabalho" in baixo
        or "termo de rescisao do contrato de trabalho" in baixo
    )
    mantidos = list(candidatos)
    if formulario and not dispensa_propria:
        mantidos = [item for item in mantidos if item["tipo"] != "comunicacao_dispensa"]
        if ("termo de quitação" in baixo or "termo de quitacao" in baixo) and not titulo_trct:
            mantidos = [item for item in mantidos if item["tipo"] != "termo_rescisao"]
    if any(sinal in baixo for sinal in ("comprovante de pagamento de darf", "darf/darf", "convenio rfb-darf", "documento de arrecada")):
        mantidos = [item for item in mantidos if item["tipo"] != "comprovante_transferencia"]
    if mencao_administrativa(texto):
        mantidos = [
            item
            for item in mantidos
            if item["tipo"] not in {"balancete", "folha_pagamento", "extrato_bancario"}
        ]
        if _oficio_so_no_nome_de_arquivo(texto):
            mantidos = [item for item in mantidos if item["tipo"] != "oficio_encaminhamento"]
    return mantidos


def dividir_dispensa_e_transferencia(texto: str, palavras: list[dict]) -> float | None:
    """Corte relativo quando a dispensa e a transferência estão no mesmo recorte."""
    baixo = _normalizar(texto)
    if "dispensa" not in baixo or "transfer" not in baixo:
        return None
    alturas = [float(palavra["y"]) for palavra in palavras if "transfer" in (palavra.get("texto") or "").lower()]
    if not alturas:
        return None
    inicio_transferencia = min(alturas)
    corte = inicio_transferencia - 0.03
    for palavra in palavras:
        if not re.search(r"banco", palavra.get("texto") or "", flags=re.IGNORECASE):
            continue
        y = float(palavra["y"])
        if inicio_transferencia - 0.08 <= y < inicio_transferencia:
            corte = min(corte, y - 0.012)
    if corte <= 0.2 or corte >= 0.85:
        return None
    return round(corte, 4)


def dividir_transferencia_e_holerite(texto: str, palavras: list[dict]) -> float | None:
    """Corte relativo quando o comprovante e o holerite estão no mesmo recorte."""
    baixo = _normalizar(texto)
    if "transfer" not in baixo:
        return None
    if "demonstrativo de pagamento" not in baixo and "total de proventos" not in baixo and "total líquido" not in baixo:
        return None
    alturas = [
        float(palavra["y"])
        for palavra in palavras
        if re.search(r"demonstrativo|proventos|funcion", palavra.get("texto") or "", flags=re.IGNORECASE)
    ]
    if not alturas:
        return None
    corte = min(alturas) - 0.02
    if corte <= 0.12 or corte >= 0.88:
        return None
    return round(corte, 4)


def segmentar_regioes(texto: str, candidatos: list[dict]) -> list[dict]:
    """
    Heurística de segmentação vertical quando há múltiplos tipos na mesma página.
    Coordenadas são relativas (0–1) à página.
    Página sem candidato tipado não gera peça placeholder.
    """
    if not candidatos:
        return []
    unicos = []
    vistos = set()
    for item in candidatos:
        if item["tipo"] in vistos or item["tipo"] == "outros_nao_classificados":
            continue
        vistos.add(item["tipo"])
        unicos.append(item)
    if not unicos:
        return []
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
                "placeholder": False,
            }
        ]
    # Ordena transferência acima do holerite quando ambos aparecem.
    prioridade = {
        "comprovante_transferencia": 0,
        "holerite": 1,
        "darf": 0,
        "comprovante_darf": 1,
        "guia_fgts": 0,
        "comprovante_fgts": 1,
        "termo_rescisao": 0,
        "termo_quitacao": 1,
        "comunicacao_dispensa": 2,
    }
    unicos.sort(key=lambda item: prioridade.get(item["tipo"], 50))
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
                "placeholder": False,
            }
        )
    return regioes


def recortar_texto_para_tipo(texto: str, tipo: str, outros_tipos: list[str] | None = None) -> str:
    """
    Recorta o texto da página priorizando o trecho do tipo solicitado.
    Quando há múltiplas peças, evita misturar campos entre regiões.
    """
    if not texto or not tipo:
        return texto or ""
    outros = [t for t in (outros_tipos or []) if t and t != tipo]
    if not outros:
        return texto
    from aplicacao.laboratorio.catalogo import CATALOGO_TIPOS

    chaves_tipo = next((list(item.palavras_chave) for item in CATALOGO_TIPOS if item.codigo == tipo), [])
    if not chaves_tipo:
        return texto
    baixo = _normalizar(texto)
    posicoes = []
    for chave in chaves_tipo:
        pos = baixo.find(chave)
        if pos >= 0:
            posicoes.append(pos)
    if not posicoes:
        return texto
    inicio = min(posicoes)
    fim = len(texto)
    for outro in outros:
        chaves_outro = next((list(item.palavras_chave) for item in CATALOGO_TIPOS if item.codigo == outro), [])
        for chave in chaves_outro:
            pos = baixo.find(chave)
            if pos > inicio:
                fim = min(fim, max(pos, inicio + 80))
    # Expande um pouco para cima para capturar cabeçalho próximo.
    inicio = max(0, inicio - 120)
    recorte = texto[inicio:fim].strip()
    return recorte if len(recorte) >= 40 else texto
