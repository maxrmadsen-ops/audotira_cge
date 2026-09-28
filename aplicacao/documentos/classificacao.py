"""Classificação determinística. Evidência estrutural precede indício genérico."""

import re
import unicodedata
from decimal import Decimal

from django.conf import settings

from aplicacao.documentos.escolhas import MetodoClassificacao, TipoDocumento

SINAIS = (
    (TipoDocumento.NOTA_FISCAL, ("nota fiscal", "danfe")),
    (TipoDocumento.FOLHA_PAGAMENTO, ("folha de pagamento", "holerite", "contra cheque", "contracheque")),
    (TipoDocumento.EXTRATO_BANCARIO, ("extrato bancario", "extrato da conta")),
    (TipoDocumento.COMPROVANTE_BANCARIO, ("comprovante bancario", "comprovante de pagamento", "comprovante de transferencia")),
    (TipoDocumento.PLANO_TRABALHO, ("plano de trabalho",)),
    (TipoDocumento.PRESTACAO_FINAL, ("prestacao final",)),
    (TipoDocumento.PRESTACAO_PARCIAL, ("prestacao parcial",)),
    (TipoDocumento.RELATORIO_SIGEF, ("relatorio sigef", "sigef")),
    (TipoDocumento.RELATORIO_EXECUCAO, ("relatorio de execucao",)),
    (TipoDocumento.CADASTRO_ENTIDADE, ("cadastro de entidade", "cartao cnpj")),
    (TipoDocumento.RECIBO, ("recibo",)),
    (TipoDocumento.GUIA, ("guia de recolhimento", "darf", "gps")),
    (TipoDocumento.DECLARACAO, ("declaracao",)),
)

TITULO_TERMO = re.compile(
    r"termo de (fomento|colabora[cç][aã]o|conv[eê]nio)\s+n[.º°o]*\s*(\d+)\s*/\s*(\d{4})",
    re.IGNORECASE,
)
COMPANHEIROS = (
    ("cláusula contratual", re.compile(r"cl[aá]usula\s+[a-zà-ú0-9]+", re.IGNORECASE)),
    ("parte", re.compile(r"\b(concedente|convenente|benefici[aá]ri[oa])\b", re.IGNORECASE)),
    ("objeto", re.compile(r"\bobjeto\b", re.IGNORECASE)),
    ("recursos", re.compile(r"montante de\s+R\$|recursos financeiros|valor total\s*:", re.IGNORECASE)),
    ("vigência", re.compile(r"vig[eê]ncia", re.IGNORECASE)),
)
ESPECIE = {
    "fomento": "Termo de Fomento",
    "colaboracao": "Termo de Colaboração",
    "convenio": "Termo de Convênio",
}


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(caractere for caractere in base if not unicodedata.combining(caractere))
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _presente(sinal: str, texto: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(sinal)}(?![a-z0-9])", texto or "") is not None


def _trecho(texto: str, inicio: int, fim: int, antes: int = 24) -> str:
    corte_inicio = max(0, inicio - antes)
    corte_fim = min(len(texto), fim + 80)
    return " ".join(texto[corte_inicio:corte_fim].split())[:240]


def _especie(rotulo: str) -> str:
    normal = _normalizar(rotulo)
    for chave, nome in ESPECIE.items():
        if chave in normal:
            return nome
    return "Termo"


def _termo_estrutural(texto: str) -> dict | None:
    titulo = TITULO_TERMO.search(texto or "")
    if not titulo:
        return None
    evidencias = [
        {
            "criterio": "título numerado do instrumento",
            "trecho": _trecho(texto, titulo.start(), titulo.end(), antes=0),
        }
    ]
    for criterio, padrao in COMPANHEIROS:
        achado = padrao.search(texto)
        if achado:
            evidencias.append({"criterio": criterio, "trecho": _trecho(texto, achado.start(), achado.end())})
    if len(evidencias) < 3:
        return None
    numero = f"{titulo.group(2)}/{titulo.group(3)}"
    return {
        "tipo": TipoDocumento.TERMO,
        "subtipo": _especie(titulo.group(1)),
        "numero": numero,
        "confianca": Decimal("0.920"),
        "metodo": MetodoClassificacao.ESTRUTURAL,
        "estado": "identificado",
        "evidencias": evidencias,
        "fundamento": _fundamento("identificado", evidencias),
    }


def _localizar(sinal: str, texto: str) -> re.Match[str] | None:
    partes = []
    for caractere in sinal:
        if caractere == " ":
            partes.append(r"\s+")
            continue
        letras = {
            "a": "aáàâã",
            "e": "eéê",
            "i": "ií",
            "o": "oóôõ",
            "u": "uúü",
            "c": "cç",
        }.get(caractere, re.escape(caractere))
        partes.append(f"[{letras}]")
    return re.search(rf"(?<![A-Za-z0-9]){''.join(partes)}(?![A-Za-z0-9])", texto or "", re.IGNORECASE)


def _indicios(nome: str, texto: str) -> list[dict]:
    achados = []
    for tipo, sinais in SINAIS:
        for sinal in sinais:
            local = _localizar(sinal, texto)
            if local:
                achados.append(
                    {
                        "tipo": tipo,
                        "criterio": f"indício «{sinal}»",
                        "trecho": _trecho(texto, local.start(), local.end()),
                    }
                )
                break
            if _presente(sinal, nome):
                achados.append({"tipo": tipo, "criterio": f"nome do arquivo contém «{sinal}»", "trecho": sinal})
                break
    return achados


def _fundamento(estado: str, evidencias: list[dict]) -> str:
    rotulo = "identificado" if estado == "identificado" else "não identificado"
    linhas = [f"Estado: {rotulo}."]
    for item in evidencias:
        linhas.append(f"{item['criterio']}: {item['trecho']}")
    return "\n".join(linhas)[:2000]


def _vazio(evidencias: list[dict] | None = None) -> dict:
    evidencias = evidencias or []
    return {
        "tipo": TipoDocumento.NAO_CLASSIFICADO,
        "subtipo": "",
        "numero": "",
        "confianca": Decimal("0.000"),
        "metodo": MetodoClassificacao.NENHUM,
        "estado": "insuficiente",
        "evidencias": evidencias,
        "fundamento": _fundamento("insuficiente", evidencias) if evidencias else "Estado: não identificado. Nenhuma evidência bastante.",
    }


def classificar(nome_original: str, texto: str) -> dict:
    """Identifica um tipo só com evidência bastante. Empate ou menção isolada não escolhe tipo."""
    bruto = texto or ""
    estrutural = _termo_estrutural(bruto)
    if estrutural:
        return estrutural
    nome = _normalizar(_nome_arquivo(nome_original))
    indicios = _indicios(nome, bruto[:20000])
    tipos = []
    for item in indicios:
        if item["tipo"] not in tipos and item["criterio"].startswith("indício"):
            tipos.append(item["tipo"])
    if len(tipos) == 1:
        escolhido = next(item for item in indicios if item["tipo"] == tipos[0] and item["criterio"].startswith("indício"))
        confianca = Decimal("0.750")
        minimo = Decimal(str(settings.CLASSIFICACAO_CONFIANCA_MINIMA))
        if confianca < minimo:
            return _vazio([escolhido])
        return {
            "tipo": escolhido["tipo"],
            "subtipo": "",
            "numero": "",
            "confianca": confianca,
            "metodo": MetodoClassificacao.PALAVRAS_CHAVE,
            "estado": "identificado",
            "evidencias": [escolhido],
            "fundamento": _fundamento("identificado", [escolhido]),
        }
    if indicios:
        return _vazio(indicios)
    return _vazio()


def _nome_arquivo(nome: str) -> str:
    return (nome or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
