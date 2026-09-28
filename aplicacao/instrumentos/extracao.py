"""Estruturador determinístico. O texto do documento é dado, não instrução."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from aplicacao.instrumentos.escolhas import (
    CategoriaClausula,
    CategoriaObrigacao,
    OperadorTemporal,
    PapelParte,
    UnidadeTemporal,
)

ORDINAIS = {
    "PRIMEIRA": 1,
    "SEGUNDA": 2,
    "TERCEIRA": 3,
    "QUARTA": 4,
    "QUINTA": 5,
    "SEXTA": 6,
    "SETIMA": 7,
    "OITAVA": 8,
    "NONA": 9,
    "DECIMA": 10,
    "VIGESIMA": 20,
}
ORDINAL_TEXTO = (
    r"(?:D[EÉ]CIMA(?:\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|S[EÉ]TIMA|OITAVA|NONA))?|"
    r"VIG[EÉ]SIMA|[A-ZÁÉÍÓÚÂÊÔÃÕÇ]+)"
)
MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

INSTRUCAO = re.compile(
    r"ignore|instrucoes anteriores|instrucao anterior|voce deve|conclua que|system\s*:|assistant\s*:",
    re.IGNORECASE,
)
DINHEIRO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})")
NORMA = re.compile(
    r"((Lei Complementar|Lei Federal|Decreto|Resolu[cç][aã]o|Lei)\s+n[ºo°.]?\s*([\d.]+)\s*/\s*(\d{2,4}))",
    re.IGNORECASE,
)


def extrair_termo(texto: str) -> dict:
    bruto = texto or ""
    dados = _sem_instrucoes(bruto)
    numero, ano = _numero_termo(dados)
    concedente, beneficiario, municipio, uf = _resolver_partes(dados)
    total_texto, total = _valor_rotulado(dados, r"valor total\s*:")
    if total is None:
        total_texto, total = _valor_rotulado(dados, r"montante de")
    parcelas, parcela_texto, parcela = _parcelas(dados)
    objeto = _objeto(dados)
    clausulas = _clausulas(dados)
    destinacao = _destinacao(dados)
    vigencia_fim, vigencia_trecho = _fim_vigencia(dados)
    assinatura, assinatura_trecho = _data_assinatura(dados)
    aplicacao = next((item["aplicacao"] for item in clausulas if item["aplicacao"]), None)
    conta = next((item["conta"] for item in clausulas if item["conta"]), None)
    restituicao = _restituicao(dados)
    return {
        "tipo_instrumento": "Termo de Fomento" if numero else "",
        "numero": numero,
        "ano": ano,
        "identificacao_completa": f"Termo de Fomento nº {numero}/{ano}" if numero and ano else "",
        "processo_sgpe": _sgpe(dados),
        "municipio": municipio,
        "uf": uf,
        "objeto_integral": objeto,
        "objeto_resumo": objeto,
        "finalidade": "",
        "destinacao_recursos": destinacao,
        "data_celebracao": None,
        "data_assinatura": assinatura,
        "data_publicacao": None,
        "vigencia_inicio": None,
        "vigencia_fim": vigencia_fim,
        "duracao_texto": vigencia_trecho,
        "referencia_plano_trabalho": "Plano de Trabalho" if re.search(r"plano de trabalho", dados, re.I) else "",
        "moeda": "BRL" if total is not None else "",
        "conta_restituicao": restituicao,
        "valor_total": total,
        "valor_total_texto": total_texto,
        "quantidade_parcelas": parcelas,
        "valor_parcela": parcela,
        "valor_parcela_texto": parcela_texto,
        "partes": [
            {"papel": PapelParte.CONCEDENTE, **concedente["parte"]},
            {"papel": PapelParte.BENEFICIARIO, **beneficiario["parte"], "municipio": municipio, "uf": uf},
        ],
        "clausulas": clausulas,
        "referencias": _normas(dados),
        "trechos": {
            "identificacao": _recorte(dados, r"TERMO DE FOMENTO"),
            "processo": _recorte(dados, r"SGPe"),
            "municipio": municipio,
            "objeto": objeto,
            "valor_total": total_texto,
            "parcelas": parcela_texto,
            "finalidade": "",
            "destinacao": destinacao,
            "vigencia_fim": vigencia_trecho,
            "data_assinatura": assinatura_trecho,
            "data_publicacao": "",
            "vigencia_inicio": "",
            "aplicacao": (aplicacao or {}).get("texto", ""),
            "conta": (conta or {}).get("texto", ""),
            "conta_agencia": "",
            "conta_numero": "",
            "conta_restituicao": restituicao.get("texto", ""),
        },
    }


def consistencia_aritmetica(quantidade, parcela, total):
    if quantidade is None or parcela is None or total is None:
        return None, ""
    produto = (Decimal(quantidade) * parcela).quantize(Decimal("0.01"))
    if produto == total:
        return True, ""
    return False, (
        "A quantidade de parcelas vezes o valor da parcela não coincide com o valor total. "
        "Os valores extraídos foram mantidos."
    )


def _sem_instrucoes(texto: str) -> str:
    linhas = []
    for linha in texto.splitlines():
        if INSTRUCAO.search(_normalizar(linha)):
            continue
        linhas.append(linha)
    return "\n".join(linhas)


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(caractere for caractere in base if not unicodedata.combining(caractere))


def _numero_termo(texto: str):
    achado = re.search(r"TERMO DE FOMENTO\s+N[ºo°.]?\s*(\d+)\s*/\s*(\d{4})", texto, re.IGNORECASE)
    if not achado:
        return "", None
    return achado.group(1), int(achado.group(2))


def _sgpe(texto: str) -> str:
    achado = re.search(
        r"SGPe(?:\s+sob\s+o\s+n[úu]mero)?\s+([A-Z]{2,}\s*\d+\s*/\s*\d{4})",
        texto,
        re.IGNORECASE,
    )
    if not achado:
        return ""
    return re.sub(r"\s+", " ", achado.group(1)).strip()


def _bloco(texto: str, inicio: str, fim: str) -> str:
    achado = re.search(inicio, texto, re.IGNORECASE)
    if not achado:
        return ""
    resto = texto[achado.end() :]
    corte = re.search(fim, resto, re.IGNORECASE)
    return (resto[: corte.start()] if corte else resto).strip()


def _resolver_partes(texto: str):
    concedente = _parte(texto, r"CONCEDENTE\s*:", r"BENEFICI")
    beneficiario = _parte(texto, r"BENEFICI[AÁ]RI[AO]?\s*:", r"OBJETO\s*:|CL[AÁ]USULA")
    if concedente["parte"]["nome"] or beneficiario["parte"]["nome"]:
        municipio, uf = _municipio(beneficiario["bloco"])
        return concedente, beneficiario, municipio, uf
    return _partes_narrativas(texto)


def _parte_vazia() -> dict:
    return {
        "bloco": "",
        "parte": {
            "nome": "",
            "sigla": "",
            "cnpj": "",
            "representante_nome": "",
            "representante_cargo": "",
            "representante_cpf": "",
            "endereco": "",
            "municipio": "",
            "uf": "",
        },
    }


def _partes_narrativas(texto: str):
    corte = re.search(r"(?<!SUB)CL[AÁ]USULA\s+", texto, re.IGNORECASE)
    preambulo = texto[: corte.start()] if corte else texto
    cnpjs = list(re.finditer(r"CNPJ(?:\s+sob)?(?:\s+n[ºo°.]?)?\s*[\d./-]{14,18}", preambulo, re.IGNORECASE))
    vazio = _parte_vazia()
    if len(cnpjs) < 2:
        return vazio, vazio, "", ""
    meio = preambulo.rfind(" e a ", 0, cnpjs[1].start())
    if meio < 0:
        return vazio, vazio, "", ""
    primeiro = _campos_parte(preambulo[:meio])
    segundo_bloco = preambulo[meio + 5 :]
    segundo = _campos_parte(segundo_bloco)
    municipio, uf = _municipio(segundo_bloco)
    segundo["municipio"] = municipio
    segundo["uf"] = uf
    return {"bloco": preambulo[:meio], "parte": primeiro}, {"bloco": segundo_bloco, "parte": segundo}, municipio, uf


def _campos_parte(bloco: str) -> dict:
    limpo = _sem_instrucoes(bloco)
    cnpj = re.search(r"CNPJ(?:\s+sob)?(?:\s+n[ºo°.]?)?\s*([\d./-]{14,18})", limpo, re.IGNORECASE)
    cpf = re.search(r"CPF(?:\s+sob)?(?:\s+(?:o\s+)?)?(?:n[ºo°.]?\s*)?(\d{3}\.\d{3}\.\d{3}-\d{2})", limpo, re.IGNORECASE)
    representante = re.search(r"Representante\s*:\s*([^,\n]+)", limpo, re.IGNORECASE)
    if not representante:
        representante = re.search(
            r"Presidente,?\s*Sr\(?a\)?\.?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]{3,80}?)\s*,",
            limpo,
        )
    antes = re.split(r"CNPJ", limpo, maxsplit=1, flags=re.IGNORECASE)[0]
    nome_longo = re.search(r"((?:FUNDA[CÇ][AÃ]O|ASSOCIA[CÇ][AÃ]O).+)", antes, re.IGNORECASE | re.DOTALL)
    nome = " ".join((nome_longo.group(1) if nome_longo else antes).split()).strip(" :.—-")
    sigla = re.search(r"\(([A-Z]{2,8})\)|[—\-]\s*([A-Z]{2,8})\b", nome)
    return {
        "nome": nome,
        "sigla": (sigla.group(1) or sigla.group(2)) if sigla else "",
        "cnpj": cnpj.group(1) if cnpj else "",
        "representante_nome": " ".join(representante.group(1).split()) if representante else "",
        "representante_cargo": "Presidente" if representante and re.search(r"Presidente", limpo) else "",
        "representante_cpf": cpf.group(1) if cpf else "",
        "endereco": "",
        "municipio": "",
        "uf": "",
    }


def _parte(texto: str, inicio: str, fim: str) -> dict:
    bloco = _bloco(texto, inicio, fim)
    limpo = _sem_instrucoes(bloco)
    cnpj = re.search(r"CNPJ\s*([\d./-]{14,18})", limpo, re.IGNORECASE)
    representante = re.search(r"Representante\s*:\s*([^,\n]+)", limpo, re.IGNORECASE)
    cpf = re.search(r"CPF\s*([\d.-]{11,14})", limpo, re.IGNORECASE)
    cargo = re.search(r"cargo\s*:\s*([^\n,]+)", limpo, re.IGNORECASE)
    nome = re.split(r"CNPJ|Representante", limpo, maxsplit=1, flags=re.IGNORECASE)[0].strip(" :.—-")
    sigla = re.search(r"[—\-]\s*([A-Z]{2,8})\b", nome)
    return {
        "bloco": limpo,
        "parte": {
            "nome": nome,
            "sigla": sigla.group(1) if sigla else "",
            "cnpj": cnpj.group(1) if cnpj else "",
            "representante_nome": representante.group(1).strip() if representante else "",
            "representante_cargo": cargo.group(1).strip() if cargo else "",
            "representante_cpf": cpf.group(1) if cpf else "",
            "endereco": "",
            "municipio": "",
            "uf": "",
        },
    }


def _municipio(bloco: str):
    achado = re.search(
        r"munic[ií]pio de\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ \-]*?)\s*/\s*([A-Z]{2})",
        bloco,
        re.IGNORECASE,
    )
    if not achado:
        return "", ""
    return achado.group(1).strip().upper(), achado.group(2).upper()


def _dinheiro(token: str):
    try:
        return Decimal(token.replace(".", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def _valor_rotulado(texto: str, rotulo: str):
    achado = re.search(rotulo + r"\s*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto, re.IGNORECASE)
    if not achado:
        return "", None
    return achado.group(1), _dinheiro(achado.group(1))


def _parcelas(texto: str):
    achado = re.search(
        r"(\d+)\s*(?:\([^)]{0,60}\)\s*)?parcelas\s+de\s+R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        re.IGNORECASE,
    )
    if not achado:
        return None, "", None
    return int(achado.group(1)), achado.group(2), _dinheiro(achado.group(2))


def _objeto(texto: str) -> str:
    bloco = _bloco(texto, r"OBJETO\s*:", r"Valor total|CL[AÁ]USULA")
    if bloco:
        return " ".join(bloco.split())
    achado = re.search(r"objeto:\s*(.+?)(?:,?\s*conforme|\.\s|(?<!SUB)CL[AÁ]USULA)", texto, re.IGNORECASE | re.DOTALL)
    return " ".join(achado.group(1).split()) if achado else ""


def _destinacao(texto: str) -> str:
    achado = re.search(r"(Ser[aã]o destinados recursos financeiros[^.]{0,240})", texto, re.IGNORECASE)
    return " ".join(achado.group(1).split()) if achado else ""


def _fim_vigencia(texto: str):
    achado = re.search(
        r"(fim de vig[eê]ncia em\s+(\d{1,2}\s+de\s+[A-Za-zçãé]+)\s+de\s+(\d{4})[^.]{0,120})",
        texto,
        re.IGNORECASE,
    )
    if not achado:
        return None, ""
    data = _data_extenso(achado.group(2) + " de " + achado.group(3))
    return data, " ".join(achado.group(1).split())


def _data_assinatura(texto: str):
    achado = re.search(
        r"assinam[\s\S]{0,500}?(\d{1,2}\s+de\s+[A-Za-zçãé]+\s+de\s+\d{4})",
        texto,
        re.IGNORECASE,
    )
    if not achado:
        return None, ""
    return _data_extenso(achado.group(1)), achado.group(1)


def _data_extenso(texto: str):
    from datetime import date

    achado = re.search(r"(\d{1,2})\s+de\s+([A-Za-zçãé]+)\s+de\s+(\d{4})", texto or "", re.IGNORECASE)
    if not achado:
        return None
    mes = MESES.get(_normalizar(achado.group(2)).lower())
    if not mes:
        return None
    try:
        return date(int(achado.group(3)), mes, int(achado.group(1)))
    except ValueError:
        return None


def _restituicao(texto: str) -> dict:
    achado = re.search(
        r"(conta\s+n[ºo°.]?\s*([\dA-Za-z.-]+)[, ]+\s*ag[eê]ncia\s+n[ºo°.]?\s*([\d.-]+)\s+do\s+Banco do Brasil)",
        texto,
        re.IGNORECASE,
    )
    if not achado:
        return {"texto": "", "agencia": "", "numero_conta": ""}
    return {
        "texto": " ".join(achado.group(1).split()),
        "numero_conta": achado.group(2),
        "agencia": achado.group(3),
    }


def _numero_ordinal(ordinal: str):
    if ordinal in ORDINAIS:
        return ORDINAIS[ordinal]
    if ordinal.startswith("DECIMA "):
        complemento = ORDINAIS.get(ordinal.split(" ", 1)[1])
        if complemento:
            return 10 + complemento
    return None


def _sem_mobiliario(texto: str) -> str:
    """Retira rodapé e certificado de página, que não fazem parte da cláusula."""
    texto = re.sub(
        r"(?:Rua|Avenida|Av\.)\s+\S.{8,180}?CEP\s*\d{5}-?\d{3}\s*(?=P[aá]gina|P[aá]g\.)",
        " ",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(r"P[aá]gina\s+\d+\s+de\s+\d+", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"P[aá]g\.\s*\d+\s+de\s+\d+", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"Documento assinado digitalmente\.?", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"Para confer[eê]ncia,?\s*acesse o site\s+\S+", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(
        r"e informe o processo\s+\S+(?:\s+\S+){0,2}\s+e o c[oó]digo\s+\S+\.?",
        " ",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(r"=+\s*Q\d+\s*-?", " ", texto)
    return texto


def _clausulas(texto: str) -> list[dict]:
    pedacos = re.split(r"(?<!SUB)(?=CL[AÁ]USULA\s+)", _sem_mobiliario(texto), flags=re.IGNORECASE)
    saida = []
    for pedaco in pedacos:
        cabeca = re.match(
            rf"CL[AÁ]USULA\s+({ORDINAL_TEXTO})\s*(?:[—\-:.]+\s*)?(.*)",
            pedaco.strip(),
            re.IGNORECASE | re.DOTALL,
        )
        if not cabeca:
            continue
        ordinal = _normalizar(cabeca.group(1)).upper()
        resto = cabeca.group(2).strip()
        linhas = resto.splitlines()
        titulo = (linhas[0] if linhas else "").strip()[:255]
        corpo = "\n".join(linhas[1:]).strip() if len(linhas) > 1 else resto
        saida.append(
            {
                "ordinal": ordinal,
                "numero": _numero_ordinal(ordinal),
                "titulo": titulo,
                "texto": corpo or resto,
                "categoria": _categoria(ordinal, titulo, corpo or resto),
                "regras_temporais": _regras_temporais(resto),
                "obrigacao": _obrigacao(ordinal, resto),
                "aplicacao": _aplicacao(ordinal, resto),
                "conta": _conta(resto),
                "consequencia": _consequencia(resto),
            }
        )
    return saida


def _categoria(ordinal: str, titulo: str, corpo: str) -> str:
    base = _normalizar(f"{titulo} {corpo}").lower()
    if "banco do brasil" in base or "conta corrente" in base:
        return CategoriaClausula.CONTA_BANCARIA
    if ordinal == "SETIMA" or "aplicacao financeira" in base:
        return CategoriaClausula.APLICACAO_FINANCEIRA
    if any(sinal in base for sinal in ("multa", "rescis", "devolu", "sanc")):
        return CategoriaClausula.PENALIDADE
    if ordinal in {"QUINTA", "SEXTA"} or "vigencia" in base or "prazo" in base:
        return CategoriaClausula.TEMPORAL
    if "objeto" in base:
        return CategoriaClausula.OBJETO
    if "recurso" in base:
        return CategoriaClausula.RECURSOS
    return CategoriaClausula.OUTRA


def _regras_temporais(corpo: str) -> list[dict]:
    regras = []
    meses = re.search(r"(\d+)\s+meses\s+(a partir d[eao]|durante|ap[óo]s)\s+([^\n.]+)", corpo, re.IGNORECASE)
    if meses:
        regras.append(_regra(int(meses.group(1)), UnidadeTemporal.MESES, _operador(meses.group(2)), meses.group(3), corpo))
    dias = re.search(
        r"(\d+)\s+dias?(?:\s+(uteis|úteis|corridos))?\s+(ap[óo]s|antes de|at[ée]|dentro de)\s+([^\n.]+)",
        corpo,
        re.IGNORECASE,
    )
    if dias:
        unidade = UnidadeTemporal.DIAS_UTEIS if dias.group(2) and "util" in _normalizar(dias.group(2)).lower() else UnidadeTemporal.DIAS_CORRIDOS
        regras.append(_regra(int(dias.group(1)), unidade, _operador(dias.group(3)), dias.group(4), corpo))
    for achado in re.finditer(r"(\d+)\s*(?:\([^)]{0,80}\)\s*)?(dias?|meses|anos?)\b", corpo, re.IGNORECASE):
        janela = corpo[max(0, achado.start() - 90) : achado.end() + 140]
        if not re.search(r"prazo|contad|vig[eê]nc|anterior|improrrog", janela, re.IGNORECASE):
            continue
        unidade = _unidade_temporal(achado.group(2))
        operador = _operador(janela)
        inicio = max(0, achado.start() - 90)
        destino = janela[achado.end() - inicio :].strip(" ,.;")
        regras.append(_regra(int(achado.group(1)), unidade, operador, destino[:160], janela))
    fim = re.search(r"fim de vig[eê]ncia em\s+(\d{1,2}\s+de\s+[A-Za-zçãé]+\s+de\s+\d{4})", corpo, re.IGNORECASE)
    if fim:
        regras.append(
            {
                "quantidade": None,
                "unidade": "",
                "operador": "",
                "evento_origem": "data escrita no documento",
                "evento_destino": "fim de vigência",
                "condicao": "",
                "trecho": " ".join(fim.group(0).split()),
                "data_documental": _data_extenso(fim.group(1)),
                "data_calculada": None,
                "calculo": "Data escrita no documento. Nenhum prazo foi somado a ela.",
            }
        )
    unicas = []
    vistas = set()
    for regra in regras:
        chave = (regra["quantidade"], regra["unidade"], regra["evento_destino"][:40])
        if chave in vistas:
            continue
        vistas.add(chave)
        unicas.append(regra)
    return unicas


def _unidade_temporal(texto: str) -> str:
    normal = _normalizar(texto).lower()
    if normal.startswith("ano"):
        return UnidadeTemporal.ANOS
    if normal.startswith("mes"):
        return UnidadeTemporal.MESES
    if "util" in normal:
        return UnidadeTemporal.DIAS_UTEIS
    return UnidadeTemporal.DIAS_CORRIDOS


def _regra(quantidade: int, unidade: str, operador: str, destino: str, trecho: str) -> dict:
    return {
        "quantidade": quantidade,
        "unidade": unidade,
        "operador": operador,
        "evento_destino": " ".join(destino.split())[:160],
        "evento_origem": " ".join(destino.split())[:160],
        "condicao": "",
        "trecho": " ".join(trecho.split())[:1000],
        "data_calculada": None,
        "data_documental": None,
        "calculo": "Prazo relativo. Data não calculada: o marco não foi convertido em data absoluta.",
    }


def _operador(texto: str) -> str:
    normal = _normalizar(texto).lower()
    if "partir" in normal:
        return OperadorTemporal.A_PARTIR_DE
    if "antes" in normal or "anterior" in normal or "anteced" in normal:
        return OperadorTemporal.ANTES_DE
    if "dentro" in normal:
        return OperadorTemporal.DENTRO_DE
    if "durante" in normal:
        return OperadorTemporal.DURANTE
    if normal.startswith("ate"):
        return OperadorTemporal.ATE
    return OperadorTemporal.APOS


def _sujeito(corpo: str) -> str:
    if re.search(r"benefici", corpo, re.IGNORECASE):
        return "Beneficiário"
    if re.search(r"associa", corpo, re.IGNORECASE):
        return "Associação"
    if re.search(r"convenente", corpo, re.IGNORECASE):
        return "Convenente"
    if re.search(r"concedente", corpo, re.IGNORECASE):
        return "Concedente"
    return ""


def _obrigacao(ordinal: str, corpo: str):
    if not re.search(
        r"deve|aplicar|aplicará|aplicara|regulariz|obriga-se|obrigado|dever[aã]o|ser[aã]o transferidos|ser[aá] suspensa",
        corpo,
        re.IGNORECASE,
    ):
        return None
    sujeito = _sujeito(corpo)
    categoria = CategoriaObrigacao.OUTRA
    evidencia = ""
    if ordinal == "SETIMA" or re.search(r"da aplica[cç][aã]o financeira", corpo[:120], re.IGNORECASE):
        categoria = CategoriaObrigacao.APLICACAO_FINANCEIRA
        evidencia = "comprovante de aplicação ou extrato"
    elif re.search(r"conta corrente|banco do brasil", corpo, re.IGNORECASE):
        categoria = CategoriaObrigacao.CONTA_BANCARIA
        evidencia = "documento cadastral da conta"
    elif re.search(r"prestacao de contas|prestação de contas", corpo, re.IGNORECASE):
        categoria = CategoriaObrigacao.PRESTACAO_CONTAS
        evidencia = "relatório"
    condicao = ""
    condicao_achado = re.search(
        r"((?:enquanto|condicionad[ao]|em caso de|quando)[^.]{0,220})",
        corpo,
        re.IGNORECASE,
    )
    if condicao_achado:
        condicao = " ".join(condicao_achado.group(1).split())
    prazo = re.search(
        r"((?:no prazo|prazo de|prazo m[aá]ximo|prazo m[ií]nimo)[^.]{0,160})",
        corpo,
        re.IGNORECASE,
    )
    return {
        "sujeito": sujeito,
        "texto": " ".join(corpo.split())[:2000],
        "categoria": categoria,
        "evidencia_esperada": evidencia,
        "condicao": condicao,
        "prazo_texto": " ".join(prazo.group(1).split()) if prazo else "",
    }


def _aplicacao(ordinal: str, corpo: str):
    if ordinal != "SETIMA" and not re.search(r"da aplica[cç][aã]o financeira", corpo[:120], re.IGNORECASE):
        return None
    rendimentos = re.search(r"(rendimentos[^.]{0,180})", corpo, re.IGNORECASE)
    condicao = re.search(r"(enquanto[^.]{0,180})", corpo, re.IGNORECASE)
    return {
        "texto": " ".join(corpo.split())[:2000],
        "sujeito": _sujeito(corpo),
        "condicao": " ".join(condicao.group(1).split()) if condicao else "",
        "destinacao_rendimentos": " ".join(rendimentos.group(1).split()) if rendimentos else "",
        "evidencia_esperada": "comprovante de aplicação ou extrato",
    }


def _conta(corpo: str):
    normal = _normalizar(corpo).lower()
    if "banco do brasil" not in normal:
        return None
    if re.search(r"devolv|restitu", normal) and not re.search(r"abertura de conta|conta especifica|conta corrente junto", normal):
        return None
    agencia = re.search(r"ag[eê]ncia\s+n?[ºo°.]?\s*(\d[\d-]*)", corpo, re.IGNORECASE)
    numero = re.search(r"conta(?:\s+corrente)?\s+n[ºo°.]?\s*(\d[\d-]*)", corpo, re.IGNORECASE)
    if re.search(r"devolv|restitu", normal):
        agencia = None
        numero = None
    return {
        "instituicao": "Banco do Brasil",
        "tipo_conta": "conta corrente" if re.search(r"conta corrente", corpo, re.IGNORECASE) else "",
        "agencia": agencia.group(1) if agencia else "",
        "numero_conta": numero.group(1) if numero else "",
        "texto": " ".join(corpo.split())[:2000],
        "evidencia_esperada": "extrato bancário",
    }


def _consequencia(corpo: str):
    if not re.search(r"multa|rescis|devolu|san[cç]|ser[aá] suspensa|tomada de contas", corpo, re.IGNORECASE):
        return None
    percentual = re.search(r"(\d+(?:,\d+)?)\s*%", corpo)
    return {
        "texto": " ".join(corpo.split()),
        "percentual": _dinheiro(percentual.group(1).replace(".", "") + ",00") if percentual and "," not in percentual.group(1) else (
            Decimal(percentual.group(1).replace(",", ".")) if percentual else None
        ),
        "trecho": corpo.strip(),
    }


def _normas(texto: str) -> list[dict]:
    vistas = []
    for achado in NORMA.finditer(texto):
        tipo = achado.group(2)
        esfera = "federal" if re.search(r"federal", tipo, re.IGNORECASE) else ""
        item = {
            "tipo": tipo,
            "numero": achado.group(3),
            "ano": achado.group(4),
            "esfera": esfera,
            "texto": re.sub(r"\s+", " ", achado.group(1)).strip(),
        }
        if item["texto"] not in {existente["texto"] for existente in vistas}:
            vistas.append(item)
    return vistas


def _recorte(texto: str, padrao: str) -> str:
    achado = re.search(padrao + r".{0,80}", texto, re.IGNORECASE)
    return achado.group(0).strip() if achado else ""
