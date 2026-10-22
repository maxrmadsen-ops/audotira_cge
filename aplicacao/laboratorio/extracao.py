"""Extração estruturada local por tipo. Não preenche ausência com suposição."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from aplicacao.laboratorio.esquemas import esquema_do_tipo


def _moeda_para_decimal(texto: str) -> Decimal | None:
    limpo = (texto or "").strip()
    if not limpo:
        return None
    limpo = limpo.replace("R$", "").replace(" ", "")
    if "," in limpo and "." in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")
    try:
        return Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None


def texto_moeda(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    formatado = f"{valor:,.2f}"
    return "R$ " + formatado.replace(",", "X").replace(".", ",").replace("X", ".")


def liquido_deterministico(proventos: Decimal | None, descontos: Decimal | None) -> Decimal | None:
    if proventos is None or descontos is None:
        return None
    return proventos - descontos


def _buscar(padroes: tuple[str, ...], texto: str, flags=re.IGNORECASE | re.MULTILINE) -> str:
    for padrao in padroes:
        achado = re.search(padrao, texto or "", flags=flags)
        if achado:
            grupo = achado.group(1) if achado.lastindex else achado.group(0)
            return (grupo or "").strip()
    return ""


CHAVES_MOEDA = {
    "valor",
    "valor_liquido",
    "total_proventos",
    "total_descontos",
    "irrf",
    "inss",
    "salario_base",
    "total_bruto",
    "deducoes",
    "total_liquido",
    "valor_quitado",
    "valor_recolhimento",
    "liquido_calculado",
    "base_recolhimento",
    "encargos",
    "saldo_inicial",
    "saldo_final",
    "fgts_mes",
    "base_inss",
    "base_fgts",
    "base_irrf",
}


def _trecho(texto: str, valor: str, janela: int = 80) -> str:
    """Devolve a linha integral da evidência, sem cortar palavra no meio."""
    del janela
    alvo = (valor or "").strip()
    if not alvo:
        return ""
    for linha in (texto or "").splitlines():
        if alvo.lower() not in linha.lower():
            continue
        limpa = linha.strip()
        if _linha_mistura_outro_campo(limpa, alvo):
            return alvo
        return limpa
    return alvo


def _linha_preferida(texto: str, valor: str, acompanhamento: str = "") -> str:
    if not valor:
        return ""
    linhas = [linha.strip() for linha in (texto or "").splitlines() if valor.lower() in linha.lower()]
    if acompanhamento:
        for linha in linhas:
            if acompanhamento.lower() in linha.lower():
                return linha
    return linhas[-1] if linhas else ""


def _linha_mistura_outro_campo(linha: str, valor: str) -> bool:
    baixo = linha.lower()
    valor_baixo = valor.lower()
    vizinhos = (
        "demonstrativo de pagamento",
        "certifico que",
        "transferido para",
        "banco do brasil",
    )
    return any(vizinho in baixo and vizinho not in valor_baixo for vizinho in vizinhos)


CHAVES_DATA = {
    "data_admissao",
    "data_aviso",
    "data_desligamento",
    "data_comunicacao",
    "data",
    "data_recebimento",
}


def extrair_campos(tipo: str, texto: str, numero_pagina: int, metodo: str) -> list[dict]:
    from aplicacao.laboratorio.validacao import data_rejeitada_no_texto, data_valida_no_texto

    esquema = esquema_do_tipo(tipo)
    mapeados = _extratores.get(tipo, _extrair_generico)(texto)
    campos = []
    for item in esquema:
        original = mapeados.get(item.chave, "")
        normalizado = original
        if item.chave in CHAVES_DATA and original:
            valida = data_valida_no_texto(original)
            rejeitada = data_rejeitada_no_texto(original)
            if valida:
                original = valida
                normalizado = valida
            elif rejeitada:
                mapeados[f"{item.chave}__confianca"] = "inconsistente"
                mapeados[f"{item.chave}__evidencia"] = f"Formato de data rejeitado: {rejeitada}."
                mapeados[f"{item.chave}__metodo"] = "validacao_semantica"
                original = ""
                normalizado = ""
        if item.chave in CHAVES_MOEDA:
            decimal = _moeda_para_decimal(original) if original else None
            if item.chave == "liquido_calculado" and not original:
                bruto = _moeda_para_decimal(mapeados.get("total_bruto", ""))
                deducoes = _moeda_para_decimal(mapeados.get("deducoes", ""))
                if bruto is not None and deducoes is not None:
                    decimal = liquido_deterministico(bruto, deducoes)
                    mapeados["liquido_calculado__metodo"] = "calculo"
                    mapeados["liquido_calculado__confianca"] = "calculo"
                else:
                    decimal = liquido_deterministico(
                        _moeda_para_decimal(mapeados.get("total_proventos", "")),
                        _moeda_para_decimal(mapeados.get("total_descontos", "")),
                    )
                original = texto_moeda(decimal) if decimal is not None else ""
            normalizado = str(decimal) if decimal is not None else ""
        campos.append(
            {
                "esquema": tipo,
                "chave": item.chave,
                "rotulo": item.rotulo,
                "valor_original": original,
                "valor_normalizado": normalizado,
                "numero_pagina": numero_pagina,
                "trecho_evidencia": mapeados.get(f"{item.chave}__evidencia") or (_trecho(texto, original) if original else ""),
                "metodo": mapeados.get(f"{item.chave}__metodo") or (metodo if original else "nao_localizado"),
                "estado_confianca": mapeados.get(f"{item.chave}__confianca") or ("evidencia_textual" if original else "ausente"),
                "obrigatorio": item.obrigatorio,
            }
        )
    return campos


def _nome_trabalhador(texto: str) -> str:
    # Holerite escaneado: cabeçalho "Nome do Funcionário" e linha seguinte com o nome.
    apos_rotulo = re.search(
        r"(?:nome\s+do\s+funcion[aá]rio|cadastro)[^\n]{0,120}\n\s*(?:\d{1,6}\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç .']{6,70})",
        texto or "",
        flags=re.IGNORECASE,
    )
    if apos_rotulo:
        candidato = re.sub(r"\s+", " ", apos_rotulo.group(1)).strip(" :-|")
        if len(candidato.split()) >= 2 and "APAE" not in candidato.upper():
            return candidato
    padroes = (
        r"(?:nome\s+do\s+empregado|nome\s+do\s+funcion[aá]rio|funcion[aá]rio|empregado|trabalhador)\s*[:\-]\s*([^\n:]{3,80})",
        r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}){2,5})\b",
    )
    bloqueados = {
        "BANCO DO BRASIL",
        "COMPROVANTE DE",
        "TOTAL DE",
        "DEPARTAMENTO",
        "SEGUNDA VIA",
        "ASSOCIACAO",
        "ASSOCIAÇÃO",
        "RECIBO DE PAGAMENTO",
        "DEMONSTRATIVO DE",
        "APAE MRD",
        "APAE ASSOC",
        "MARIA ROSALINA",
        "AMIGOS",
        "EXCEP",
        "DEMONSTRATIVO",
        "NORMAIS",
        "PRESIDENTE",
    }
    for padrao in padroes:
        for achado in re.finditer(padrao, texto or "", flags=re.IGNORECASE):
            nome = re.sub(r"\s+", " ", achado.group(1)).strip(" :-|")
            if any(bloco in nome.upper() for bloco in bloqueados):
                continue
            if len(nome.split()) >= 2 and not re.search(r"\d", nome):
                return nome
    return ""


def _moeda_no_contexto(texto: str, rotulos: tuple[str, ...]) -> str:
    for rotulo in rotulos:
        achado = re.search(
            rf"{rotulo}\s*[:\-]?\s*(R\$\s*)?([0-9]{{1,3}}(?:\.[0-9]{{3}})*,[0-9]{{2}}|[0-9]+,[0-9]{{2}})",
            texto or "",
            flags=re.IGNORECASE,
        )
        if achado:
            return (achado.group(0).split(":")[-1] if ":" in achado.group(0) else achado.group(2)).strip()
        # valor na mesma linha ou na seguinte
        achado = re.search(
            rf"{rotulo}[^\n]{{0,40}}?(R\$\s*[0-9.,]+|[0-9]{{1,3}}(?:\.[0-9]{{3}})*,[0-9]{{2}})",
            texto or "",
            flags=re.IGNORECASE,
        )
        if achado:
            return achado.group(1).strip()
    return ""


def _extrair_holerite(texto: str) -> dict[str, str]:
    funcionario = _nome_trabalhador(texto)
    cargo = _buscar(
        (
            rf"{re.escape(funcionario.split()[0]) if funcionario else 'FUNCIONARIO'}[^\n]{{0,40}}\n\s*([A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]{{3,40}})\s+Data\s+Admiss",
            r"(?:cargo|fun[cç][aã]o)\s*[:\-]?\s*(?!presidente)([^\n]{3,60})",
            r"\b(Professor|Professora|Assistente|Auxiliar|Coordenador[a]?|Cuidador[a]?)\b",
        ),
        texto,
    )
    if cargo.lower().startswith("presidente"):
        cargo = _buscar((r"\b(Professor|Professora|Assistente|Auxiliar|Coordenador[a]?|Cuidador[a]?)\b",), texto)
    bases = _mapa_bases(texto)
    salario_base = _moeda_no_contexto(texto, ("sal[aá]rio[\\s\\-]?base",)) or bases.get("salario_base", "")
    base_inss = _valor_rotulo(texto, r"sal\s*cont\s*inss|base.{0,16}inss") or bases.get("base_inss", "")
    base_fgts = _valor_rotulo(texto, r"bas\w*\s*c[aá]lc\w*\s*fgts|base.{0,16}fgts", evitar=(r"m[eê]s",)) or bases.get(
        "base_fgts", ""
    )
    fgts_mes = _valor_rotulo(texto, r"fgts\s*m[eê]s") or bases.get("fgts_mes", "")
    base_irrf = _valor_rotulo(texto, r"bas\w*\s*c[aá]lc\w*\s*irrf|base.{0,20}irrf", evitar=(r"faixa",)) or bases.get(
        "base_irrf", ""
    )
    data_recebimento = _buscar((r"recebi\s+em\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto)
    responsavel = _responsavel_atesto(texto)
    cpf_atesto = _cpf_atesto(texto)
    partes_base = []
    if base_inss:
        partes_base.append(f"INSS: {base_inss}")
    if base_fgts:
        partes_base.append(f"FGTS: {base_fgts}")
    if fgts_mes:
        partes_base.append(f"FGTS do mês: {fgts_mes}")
    if base_irrf:
        partes_base.append(f"IRRF: {base_irrf}")
    assinatura = []
    if data_recebimento:
        assinatura.append(f"Recebi em {data_recebimento}")
    if re.search(r"\bassinatura\b", texto or "", flags=re.IGNORECASE):
        assinatura.append("Assinatura presente no documento")
    return {
        "empregador": _empregador(texto),
        "cnpj_empregador": _buscar((r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b",), texto),
        "funcionario": funcionario,
        "matricula": _matricula(texto),
        "identificadores": "",
        "cargo": cargo,
        "cbo": _cbo(texto),
        "competencia": _competencia(texto),
        "referencia_pagamento": "Mensal" if re.search(r"\bMensal\b", texto or "") else "",
        "data_admissao": _buscar(
            (r"(?:admiss[aã]o|data de admiss[aã]o)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",),
            texto,
        ),
        "salario_base": salario_base,
        "total_proventos": _buscar((r"Total\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s+[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}",), texto)
        or _moeda_no_contexto(texto, ("total\\s+de\\s+proventos", "proventos")),
        "total_descontos": _buscar((r"Total\s+[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",), texto)
        or _moeda_no_contexto(texto, ("total\\s+de\\s+descontos", "descontos")),
        "valor_liquido": _moeda_no_contexto(texto, ("total\\s+l[ií]quido", "l[ií]quido\\s+a\\s+receber", "valor\\s+l[ií]quido", "l[ií]quido")),
        "irrf": _valor_rotulo(texto, r"\birrf\b", evitar=(r"base", r"faixa", r"c[aá]lc"), ultimo=True)
        or _valor_rotulo(texto, r"^\s*920\b", ultimo=True),
        "inss": _valor_rotulo(texto, r"\binss\b", evitar=(r"base", r"sal\s*cont", r"c[aá]lc"), ultimo=True),
        "rubricas_proventos": _listar_rubricas(texto, "provento"),
        "rubricas_descontos": _listar_rubricas(texto, "desconto"),
        "base_inss": base_inss,
        "base_fgts": base_fgts,
        "fgts_mes": fgts_mes,
        "base_irrf": base_irrf,
        "bases_calculo": " · ".join(partes_base),
        "data_recebimento": data_recebimento,
        "assinaturas": " · ".join(assinatura),
        "responsavel_atesto": responsavel,
        "cpf_atesto": cpf_atesto,
        "liquido_calculado": "",
        "salario_base__evidencia": _linha_preferida(texto, salario_base, fgts_mes),
        "base_inss__evidencia": _linha_preferida(texto, base_inss, fgts_mes or salario_base),
        "base_fgts__evidencia": _linha_preferida(texto, base_fgts, fgts_mes or salario_base),
        "fgts_mes__evidencia": _linha_preferida(texto, fgts_mes, salario_base),
        "base_irrf__evidencia": _linha_preferida(texto, base_irrf, salario_base),
    }


def _empregador(texto: str) -> str:
    especifico = re.search(
        r"APAE\s+ASSOC\.?\s*DE\s+PAIS\s+E\s+AMIGOS\s+DOS\s+EXCEP\.?",
        texto or "",
        flags=re.IGNORECASE,
    )
    if especifico:
        nome = re.sub(r"\s+", " ", especifico.group(0)).strip()
        nome = re.sub(r"ASSOC\.?\s*DE", "ASSOC. DE", nome, count=1, flags=re.IGNORECASE)
        if not nome.endswith("."):
            nome += "."
        return nome
    generico = _buscar((r"(?:empregador|empresa|raz[aã]o social)\s*[:\-]\s*([^\n]{3,80})",), texto)
    return re.split(r"demonstrativ|compet[eê]ncia", generico, maxsplit=1, flags=re.IGNORECASE)[0].strip(" .-|")


def _cbo(texto: str) -> str:
    direto = _buscar((r"\bCBO\b\s*[:\-]?\s*(\d{4,6})\b",), texto)
    if direto:
        return direto
    linhas = (texto or "").splitlines()
    for indice, linha in enumerate(linhas[:-1]):
        if not re.search(r"\bCBO\b", linha, flags=re.IGNORECASE):
            continue
        codigos = re.findall(r"\b(\d{4,6})\b", linhas[indice + 1])
        if codigos:
            return codigos[0]
    return ""


def _matricula(texto: str) -> str:
    achado = re.search(r"cadastro[^\n]{0,40}\n\s*(\d{1,6})\b", texto or "", flags=re.IGNORECASE)
    if not achado:
        achado = re.search(r"(?:matr[ií]cula|cadastro)\s*[:\-]?\s*(\d{1,6})\b", texto or "", flags=re.IGNORECASE)
    if not achado:
        return ""
    return achado.group(1)


def _competencia(texto: str) -> str:
    rotulada = _buscar(
        (r"(?:compet[eê]ncia|m[eê]s/?ano)\s*[:\-]\s*([0-9]{1,2}[/.\-][0-9]{2,4})",),
        texto,
    )
    if rotulada:
        return rotulada
    mensal = re.search(r"\b((?:0?[1-9]|1[0-2])[/.\-]20[0-9]{2})\s+Mensal\b", texto or "", flags=re.IGNORECASE)
    if mensal:
        return mensal.group(1)
    for achado in re.finditer(r"(?<![\d/])((?:0?[1-9]|1[0-2])[/.\-]20[0-9]{2})\b", texto or ""):
        return achado.group(1)
    return ""


def _valor_rotulo(texto: str, padrao: str, evitar: tuple[str, ...] = (), ultimo: bool = False) -> str:
    moeda = r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}"
    for linha in (texto or "").splitlines():
        achado = re.search(padrao, linha, flags=re.IGNORECASE)
        if not achado:
            continue
        if any(re.search(item, linha, flags=re.IGNORECASE) for item in evitar):
            continue
        if re.search(r"certifico|presidente|cpf", linha, flags=re.IGNORECASE):
            continue
        if ultimo:
            valores = re.findall(moeda, linha)
            if valores:
                return valores[-1]
            continue
        resto = linha[achado.end() :]
        corte = re.search(r"\b(?:sal[aá]rio|sal\s*cont|bas\w*|fgts|faixa|dep)\b", resto, flags=re.IGNORECASE)
        if corte:
            resto = resto[: corte.start()]
        valores = re.findall(moeda, resto)
        if valores:
            return valores[0]
    return ""


def _mapa_bases(texto: str) -> dict[str, str]:
    rotulos = (
        ("salario_base", r"sal[aá]rio\s*base"),
        ("base_inss", r"sal\s*cont\s*inss"),
        ("base_fgts", r"bas\w*\s*c[aá]lc\w*\s*fgts"),
        ("fgts_mes", r"fgts\s*m[eê]s"),
        ("base_irrf", r"bas\w*\s*c[aá]lc\w*\s*irrf"),
    )
    linhas = (texto or "").splitlines()
    for indice, linha in enumerate(linhas[:-1]):
        posicoes = []
        for chave, padrao in rotulos:
            achado = re.search(padrao, linha, flags=re.IGNORECASE)
            if achado:
                posicoes.append((achado.start(), chave))
        if len(posicoes) < 3:
            continue
        valores = re.findall(r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}", linhas[indice + 1])
        posicoes.sort()
        return {chave: valores[ordem] for ordem, (_pos, chave) in enumerate(posicoes) if ordem < len(valores)}
    return {}


def _responsavel_atesto(texto: str) -> str:
    achado = re.search(
        r"nome\s*:\s*([A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]{5,60})",
        texto or "",
        flags=re.IGNORECASE,
    )
    if not achado:
        return ""
    nome = re.sub(r"\s+", " ", achado.group(1)).strip(" .:-")
    if re.search(r"funcion|empregad|trabalhador", nome, flags=re.IGNORECASE):
        return ""
    cargo = _buscar((r"cargo\s*:\s*(presidente|diretor[a]?|tesoureiro[a]?)",), texto)
    if cargo:
        return f"{nome} · {cargo}"
    return nome


def _cpf_atesto(texto: str) -> str:
    bloco = re.search(r"(certifico[\s\S]{0,500}|presidente[\s\S]{0,160})", texto or "", flags=re.IGNORECASE)
    if not bloco:
        return ""
    achado = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", bloco.group(0))
    return achado.group(0) if achado else ""


_RUBRICA = re.compile(
    r"^\s*(\d{1,4})\s+(.+?)\s+(?:(\d{2,3}:\d{2}\s*hs|\d{1,3},\d{2}\s*%)\s+)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*$",
    flags=re.IGNORECASE,
)


def _limpar_descricao(texto: str) -> str:
    recorte = re.split(r"certifico|errr+|que o\b|presidente|\bcpf\b", texto or "", maxsplit=1, flags=re.IGNORECASE)[0]
    recorte = re.sub(r"[|\[\]]+", " ", recorte)
    return re.sub(r"\s+", " ", recorte).strip(" .:-")


def _unidade_referencia(referencia: str) -> str:
    if re.search(r"\d{2,3}:\d{2}", referencia or ""):
        return "hs"
    if "%" in (referencia or ""):
        return "%"
    return ""


def estruturar_rubricas(texto: str) -> list[dict]:
    """Separa código, referência e valor. O percentual não vira valor monetário."""
    itens = []
    for bruta in (texto or "").splitlines():
        limpa = bruta.strip()
        if not limpa or re.search(r"certifico|presidente|\bcpf\b|\btotal\b", limpa, flags=re.IGNORECASE):
            continue
        achado = _RUBRICA.match(limpa)
        if not achado:
            continue
        codigo = achado.group(1)
        descricao = _limpar_descricao(achado.group(2))
        referencia = (achado.group(3) or "").strip()
        valor = achado.group(4)
        if re.search(r"\b(inss|irrf|faltas|vale)\b", descricao, flags=re.IGNORECASE) or codigo in {"920", "950"}:
            natureza = "desconto"
        else:
            natureza = "provento"
        decimal = _moeda_para_decimal(valor)
        descricao_limpa = bool(descricao) and len(descricao) <= 40 and not re.search(r"\d|\b[A-Za-z]\b", descricao)
        confianca = "evidencia_textual" if descricao_limpa else "parcial"
        itens.append(
            {
                "codigo": codigo,
                "descricao": descricao[:180],
                "referencia": referencia[:40],
                "unidade": _unidade_referencia(referencia),
                "natureza": natureza,
                "valor_original": valor,
                "valor_normalizado": str(decimal) if decimal is not None else "",
                "trecho_evidencia": limpa,
                "metodo": "ocr_regiao",
                "estado_confianca": confianca,
            }
        )
        if len(itens) >= 12:
            break
    return itens


def _listar_rubricas(texto: str, tipo: str) -> str:
    """Texto compatível com a leitura anterior. O OCR bruto permanece na região."""
    linhas = []
    for item in estruturar_rubricas(texto):
        if item["natureza"] != tipo:
            continue
        if item["referencia"]:
            linhas.append(f"{item['codigo']} · {item['descricao']} · {item['referencia']} · {item['valor_original']}")
        else:
            linhas.append(f"{item['codigo']} · {item['descricao']} · {item['valor_original']}")
    return "\n".join(linhas)


def _extrair_comprovante(texto: str) -> dict[str, str]:
    partes = re.split(r"transferido\s+para", texto or "", maxsplit=1, flags=re.IGNORECASE)
    origem = partes[0]
    destino = partes[1] if len(partes) > 1 else ""
    agencia_origem = _buscar((r"ag[eê]ncia\s*[:\-]?\s*([0-9]{3,6}-[0-9])",), origem)
    conta_origem = _buscar((r"conta\s*[:\-]?\s*([0-9]{2,3}(?:\.[0-9]{3})*-[0-9Xx])",), origem)
    agencia_destino = _buscar((r"ag[eê]ncia\s*[:\-]?\s*([0-9]{3,6}-[0-9])",), destino)
    conta_destino = _buscar((r"conta\s*[:\-]?\s*([0-9]{2,3}(?:\.[0-9]{3})*-[0-9Xx])",), destino)
    data_operacao, hora_operacao, impressao = _tempos_comprovante(texto or "")
    instituicao = _buscar(
        (r"(banco\s+do\s+brasil|caixa econ[oô]mica|sicredi|sicoob|bradesco|ita[uú])",),
        texto or "",
    )
    if re.search(r"banco\s+do\s+brasil", instituicao, flags=re.IGNORECASE):
        instituicao = "Banco do Brasil"
    beneficiario = _nome_conta(destino) or _buscar(
        (r"(?:favorecido|benefici[aá]rio|destinat[aá]rio)\s*[:\-]\s*([^\n]{3,80})",),
        destino or texto or "",
    )
    tipo = ""
    if re.search(r"conta\s+corrente\s+p/?\s*conta\s+corrente", texto or "", flags=re.IGNORECASE):
        tipo = "Transferência entre contas correntes"
    elif re.search(r"\b(ted|doc|pix|transfer[eê]ncia)\b", texto or "", flags=re.IGNORECASE):
        tipo = _buscar((r"\b(ted|doc|pix|transfer[eê]ncia)\b",), texto or "").capitalize()
    return {
        "instituicao": instituicao,
        "tipo_operacao": tipo,
        "titular_origem": _nome_conta(origem),
        "agencia_origem": agencia_origem,
        "conta_origem": conta_origem,
        "beneficiario": beneficiario,
        "beneficiario__evidencia": _linha_preferida(destino, beneficiario, "") if destino else "",
        "agencia_destino": agencia_destino,
        "conta_destino": conta_destino,
        "dados_destino": "",
        "data_hora": data_operacao,
        "hora_operacao": hora_operacao,
        "data_hora_impressao": impressao,
        "valor": _moeda_no_contexto(texto or "", ("valor total", "valor da transfer[eê]ncia", "valor pago", "valor")),
        "numero_documento": _buscar((r"(?:nr\.?\s*documento|nr\.?\s*docum)\s*[:\-]?\s*([0-9][0-9.\-]{8,})",), origem),
        "numero_documento_adicional": _buscar(
            (r"(?:nr\.?\s*documento|nr\.?\s*docum)\s*[:\-]?\s*([0-9][0-9.\-]{8,})",),
            destino,
        ),
        "autenticacao": _buscar(
            (r"autentica[cç][aã]o\s*[:\-]?\s*([0-9A-Za-z](?:\.\s?[0-9A-Za-z]{2,4}){3,8})",),
            texto or "",
        ),
        "identificadores": "",
        "situacao": _buscar((r"\b(efetivad[ao]|realizad[ao]|confirmad[ao]|rejeitad[ao])\b",), texto or ""),
        "agencia_origem__evidencia": _linha_preferida(texto or "", agencia_origem, conta_origem),
        "agencia_destino__evidencia": _linha_preferida(texto or "", agencia_destino, conta_destino),
        "conta_origem__evidencia": _linha_preferida(texto or "", conta_origem, ""),
        "conta_destino__evidencia": _linha_preferida(texto or "", conta_destino, ""),
    }


def _nome_conta(trecho: str) -> str:
    nome = _buscar((r"(?:cliente|titular|nome do pagador)\s*[:\-]\s*([^\n]{3,80})",), trecho)
    nome = re.split(r"\b(?:ag[eê]ncia|conta|nr\.|data|valor)\b", nome, maxsplit=1, flags=re.IGNORECASE)[0]
    return nome.strip(" :-")


def _tempos_comprovante(texto: str) -> tuple[str, str, str]:
    data = _buscar((r"data da transfer[eê]ncia\s*[:\-]?\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})",), texto)
    hora = ""
    operacao = re.search(r"banco\s+do\s+brasil\s*[-–—]\s*(\d{2}:\d{2}:\d{2})", texto, flags=re.IGNORECASE)
    if operacao:
        hora = operacao.group(1)
    impressao = ""
    cabecalho = re.search(r"(\d{2}/\d{2}/\d{2,4})\s*,\s*(\d{2}:\d{2})(?!:)", texto)
    if cabecalho and (not hora or cabecalho.group(2) != hora):
        impressao = f"{cabecalho.group(1)} {cabecalho.group(2)}"
    return data, hora, impressao


def _nome_apos_identificacao(texto: str) -> str:
    achado = re.search(
        r"(?:pis\s*/?\s*pasep|11\s*nome).{0,80}?([A-ZÁÉÍÓÚÃÕÇ]{2,}(?:\s+[A-ZÁÉÍÓÚÃÕÇ]{2,}){1,4})",
        texto or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not achado:
        return ""
    return achado.group(1).strip()[:80]


_MOEDA_PONTUADA = r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}"


_CODIGO_RESCISAO = re.compile(
    r"(?:(?<=^)|(?<=[\s\[\|/]))(\d{2,3}(?:\.\d)?)\s+(?=[A-Za-zÀ-ÿ0-9])"
)
_VALOR_RUBRICA = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}")


def liquido_lido_no_texto(texto: str) -> str:
    """Lê o líquido na faixa inferior. Não usa o salário líquido da rubrica."""
    linhas = (texto or "").splitlines()
    for indice, linha in enumerate(linhas):
        baixo = linha.lower()
        if "salário" in baixo or "salario" in baixo or "dedu" in baixo:
            continue
        if "liquido" not in baixo and "líquido" not in baixo:
            continue
        mesma = re.search(rf"l[ií]quido\s*[:\|\-]?\s*({_MOEDA_PONTUADA})", linha, flags=re.IGNORECASE)
        if mesma:
            return mesma.group(1)
        # O OCR do rodapé às vezes quebra o valor na linha seguinte.
        for seguinte in linhas[indice + 1 : indice + 4]:
            valor = re.search(rf"^[\s\|\]\[]*({_MOEDA_PONTUADA})\s*$", seguinte.strip())
            if valor:
                return valor.group(1)
    return ""


def estruturar_rubricas_rescisao(texto: str) -> list[dict]:
    """Uma rubrica por código do TRCT. Não junta a descrição do código seguinte."""
    por_codigo = {}
    ordem = []
    for bruta in (texto or "").splitlines():
        linha = re.split(
            r"total\s+bruto|total\s+dedu|valor\s+l[ií]quido",
            bruta,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        if not _VALOR_RUBRICA.search(linha):
            continue
        marcas = []
        for marca in _CODIGO_RESCISAO.finditer(linha):
            base = int(marca.group(1).split(".")[0])
            if 50 <= base <= 199:
                marcas.append(marca)
        for indice, marca in enumerate(marcas):
            codigo = marca.group(1)
            base = int(codigo.split(".")[0])
            fim = marcas[indice + 1].start() if indice + 1 < len(marcas) else len(linha)
            trecho = linha[marca.start() : fim]
            valores = _VALOR_RUBRICA.findall(trecho)
            valor = valores[0] if valores else ""
            descricao = trecho[len(codigo) :].strip()
            if valor:
                descricao = descricao.split(valor)[0]
            descricao = re.sub(r"\d{1,2}/\d{1,2}", " ", descricao)
            descricao = re.sub(r"\s+", " ", descricao).strip(" .:-|[]/()")
            if len(descricao) < 3:
                continue
            referencia = ""
            unidade = ""
            dias = re.search(r"(\d{1,2})\s*/\s*dias", trecho, flags=re.IGNORECASE)
            fracao = re.search(r"(\d{1,2}/\d{1,2})", trecho)
            if dias:
                referencia = f"{int(dias.group(1))}/dias"
                unidade = "dias"
            elif fracao:
                referencia = fracao.group(1)
            item = {
                "codigo": codigo,
                "descricao": descricao[:80],
                "referencia": referencia[:40],
                "unidade": unidade,
                "natureza": "desconto" if base >= 100 else "provento",
                "valor_original": valor,
                "valor_normalizado": str(_moeda_para_decimal(valor)) if valor else "",
                "trecho_evidencia": re.sub(r"\s+", " ", trecho).strip()[:180],
                "metodo": "ocr_regiao",
                "estado_confianca": "evidencia_textual" if valor else "ausente",
            }
            anterior = por_codigo.get(codigo)
            if anterior is not None and (anterior["valor_original"] or not valor):
                continue
            if codigo not in por_codigo:
                ordem.append(codigo)
            por_codigo[codigo] = item
            if len(ordem) >= 30:
                break
    return [por_codigo[codigo] for codigo in ordem]


def mesclar_rubricas_rescisao(texto_pagina: str, texto_tabela: str) -> list[dict]:
    """A leitura da tabela preenche valor ausente ou confirma o mesmo valor. Valor divergente fica na primeira leitura."""
    por_codigo = {}
    ordem = []
    for item in estruturar_rubricas_rescisao(texto_pagina):
        ordem.append(item["codigo"])
        por_codigo[item["codigo"]] = item
    for item in estruturar_rubricas_rescisao(texto_tabela):
        anterior = por_codigo.get(item["codigo"])
        if anterior is None:
            ordem.append(item["codigo"])
            por_codigo[item["codigo"]] = item
        elif item["valor_original"]:
            if anterior["valor_original"] and anterior["valor_original"] != item["valor_original"]:
                continue
            por_codigo[item["codigo"]] = item
    return [por_codigo[codigo] for codigo in ordem]


def _linhas_de_verba(texto: str) -> str:
    linhas = []
    for item in estruturar_rubricas_rescisao(texto):
        valor = item["valor_original"] or "valor não lido"
        linhas.append(f"{item['codigo']} {item['descricao']} {valor}")
    return "\n".join(linhas)[:800]


def _extrair_rescisao(texto: str) -> dict[str, str]:
    from aplicacao.laboratorio.validacao import datas_rotuladas_trct

    datas = datas_rotuladas_trct(texto)
    return {
        "empregador": _buscar(
            (
                r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\s+(?:\d{3,4}-)?([A-ZÁÉÍÓÚÃÕÇ].{5,70})",
                r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",
            ),
            texto,
        ),
        "trabalhador": _nome_apos_identificacao(texto) or _buscar(
            (r"(?:trabalhador|empregado|funcion[aá]rio)\s*[:\-]?\s*(.+)",),
            texto,
        ),
        "dados_vinculo": "",
        "data_admissao": datas.get("data_admissao", ""),
        "data_admissao__evidencia": datas.get("data_admissao__evidencia", ""),
        "data_aviso": datas.get("data_aviso", ""),
        "data_aviso__evidencia": datas.get("data_aviso__evidencia", ""),
        "data_desligamento": datas.get("data_desligamento", ""),
        "data_desligamento__evidencia": datas.get("data_desligamento__evidencia", ""),
        "motivo": _buscar(
            (
                r"causa do afastamento\s*\n\s*([^\n]{3,80})",
                r"(?:motivo|c[oó]digo de afastamento)\s*[:\-]?\s*(.+)",
            ),
            texto,
        ),
        "verbas_rescisorias": _linhas_de_verba(texto),
        "deducoes": _buscar((rf"total\s+dedu[cç][oõ]es\s*[:\-]?\s*({_MOEDA_PONTUADA})",), texto),
        "total_bruto": _buscar((rf"total\s+bruto\s*[,:\-]?\s*({_MOEDA_PONTUADA})",), texto),
        "total_liquido": _buscar((rf"valor\s+l[ií]quido\s*[:\|\-]?\s*({_MOEDA_PONTUADA})",), texto),
        "assinaturas": "",
    }


def _extrair_quitacao(texto: str) -> dict[str, str]:
    return {
        "empregador": _buscar(
            (
                r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\s+(?:\d{3,4}-)?([A-ZÁÉÍÓÚÃÕÇ].{5,70})",
                r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",
            ),
            texto,
        ),
        "trabalhador": _nome_apos_identificacao(texto) or _buscar((r"(?:trabalhador|empregado|funcion[aá]rio)\s*[:\-]?\s*(.+)",), texto),
        "valor_quitado": _buscar((rf"valor\s+l[ií]quido\s+de\s*R?\$?\s*({_MOEDA_PONTUADA})",), texto),
        "data": _buscar(
            (r"(?:local\s+e\s+data|data\s+da\s+quita[cç][aã]o)\s*[:\-]?\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",),
            texto,
        ),
        "assinaturas": "",
    }


def _extrair_dispensa(texto: str) -> dict[str, str]:
    from aplicacao.laboratorio.validacao import data_rejeitada_no_texto, data_valida_no_texto, motivo_rotulado, protocolo_documental

    trabalhador = _nome_apos_identificacao(texto) or _buscar(
        (
            r"nome\s*\n\s*[|\s]*([A-ZÁÉÍÓÚÃÕÇ][A-Za-zÁÉÍÓÚÃÕÇáéíóúãõç]{1,}(?:\s+[A-ZÁÉÍÓÚÃÕÇ][A-Za-zÁÉÍÓÚÃÕÇáéíóúãõç]{1,}){1,4})",
            r"(?:trabalhador|empregado|funcion[aá]rio)\s*[:\-]?\s*(.+)",
        ),
        texto,
    )
    empregador = ""
    if not re.search(r"protocolo\s+do\s+empregador", texto or "", flags=re.IGNORECASE):
        empregador = _buscar((r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",), texto)
    protocolo = protocolo_documental(texto)
    motivo = motivo_rotulado(texto)
    if motivo and re.fullmatch(r"\d{6,}", motivo) and not protocolo:
        protocolo = motivo
        motivo = ""
    data = data_valida_no_texto(texto)
    rejeitada = "" if data else data_rejeitada_no_texto(texto)
    return {
        "empregador": empregador,
        "trabalhador": trabalhador,
        "data_comunicacao": data,
        "data_comunicacao__confianca": "inconsistente" if rejeitada else "",
        "data_comunicacao__evidencia": f"Formato de data rejeitado: {rejeitada}." if rejeitada else "",
        "data_comunicacao__metodo": "validacao_semantica" if rejeitada else "",
        "motivo": motivo,
        "protocolo": protocolo,
        "protocolo__evidencia": _linha_preferida(texto, protocolo, "dispensa") if protocolo else "",
        "comprovante_recebimento": _buscar((r"(recebi|ciente).{0,40}",), texto),
    }


def _extrair_fgts(texto: str) -> dict[str, str]:
    return {
        "competencia": _buscar((r"(?:compet[eê]ncia)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "empregador": _buscar(
            (
                r"cnpj\s*/?\s*cei\s*/?\s*cpf\s*[:\-]?\s*([0-9./-]{14,20})",
                r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-\d{2})",
            ),
            texto,
        ),
        "tipo_guia": _buscar((r"(grf|grrf|guia de recolhimento)",), texto),
        "base_recolhimento": _buscar((r"(?:base(?:\s+de)?\s+c[aá]lculo|base)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "valor_recolhimento": _buscar(
            (
                r"valor\s+dep[oó]sito\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",
                r"total\s+a\s+recolher\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",
                r"(?:valor(?:\s+do)?\s+recolhimento|valor\s+total)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",
            ),
            texto,
        ),
        "encargos": _buscar(
            (
                rf"14-encargos[^\n]*\n\s*{_MOEDA_PONTUADA}\s+({_MOEDA_PONTUADA})",
                rf"(?:^|\n)\s*encargos\s*[:\-]\s*({_MOEDA_PONTUADA})",
            ),
            texto,
        ),
        "vencimento": _buscar((r"(?:vencimento)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "data_pagamento": _buscar((r"(?:pagamento|pago em)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "autenticacao": _buscar(
            (r"autentica[cç][aã]o(?:\s+sisbb)?\s*[:\-]?\s*([0-9A-Za-z](?:\.\s?[0-9A-Za-z]{2,4}){3,8})",),
            texto,
        ),
        "abrangencia": _buscar((r"(coletiv[oa]|individual)",), texto),
    }


def _extrair_generico(texto: str) -> dict[str, str]:
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    titulo = linhas[0][:120] if linhas else ""
    return {"titulo": titulo, "observacao": "", "identificador": "", "data": "", "periodo": "", "totais": ""}


_extratores = {
    "holerite": _extrair_holerite,
    "comprovante_transferencia": _extrair_comprovante,
    "termo_rescisao": _extrair_rescisao,
    "termo_quitacao": _extrair_quitacao,
    "comunicacao_dispensa": _extrair_dispensa,
    "guia_fgts": _extrair_fgts,
    "comprovante_fgts": _extrair_fgts,
    "extrato_bancario": lambda texto: {
        "instituicao": _buscar((r"(banco\s+[^\n]+)",), texto),
        "titular": _buscar((r"(?:titular|cliente)\s*[:\-]?\s*(.+)",), texto),
        "periodo": _buscar((r"(?:per[ií]odo)\s*[:\-]?\s*(.+)",), texto),
        "saldo_inicial": _buscar((r"(?:saldo anterior|saldo inicial)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "saldo_final": _buscar((r"(?:saldo atual|saldo final)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
    },
    "balancete": _extrair_generico,
    "checklist_documental": _extrair_generico,
    "oficio_encaminhamento": _extrair_generico,
    "relatorio_execucao_objeto": _extrair_generico,
    "folha_pagamento": lambda texto: {
        "competencia": _buscar((r"(?:compet[eê]ncia)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "empregador": _buscar((r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",), texto),
        "total_liquido": _buscar((r"(?:total l[ií]quido|l[ií]quido)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "quantidade_trabalhadores": _buscar((r"(?:funcion[aá]rios|empregados|trabalhadores)\s*[:\-]?\s*([0-9]+)",), texto),
    },
    "administrativo_sgpe": _extrair_generico,
    "assinaturas_autenticacoes": _extrair_generico,
    "outros_nao_classificados": _extrair_generico,
}
