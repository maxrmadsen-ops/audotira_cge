import re
from datetime import datetime
from decimal import Decimal

from aplicacao.documentos.escolhas import TipoDadoExtraido


def extrair_candidatos(paginas) -> list[dict]:
    """Extrai candidatos por expressão regular. Nenhum item aqui é fato validado."""
    encontrados = []
    vistos = set()
    for pagina in paginas:
        texto = pagina.texto_extraido or ""
        numero = pagina.numero_pagina
        for tipo, padrao, confianca, validador in _padroes():
            for ocorrencia in padrao.finditer(texto):
                valor = ocorrencia.group(1) if ocorrencia.groups() else ocorrencia.group(0)
                valor = " ".join(valor.split())
                if not valor or (validador and not validador(valor)):
                    continue
                chave = (tipo, valor, numero)
                if chave in vistos:
                    continue
                vistos.add(chave)
                inicio = max(0, ocorrencia.start() - 40)
                fim = min(len(texto), ocorrencia.end() + 40)
                encontrados.append(
                    {
                        "numero_pagina": numero,
                        "tipo": tipo,
                        "valor": valor[:255],
                        "trecho": texto[inicio:fim].strip()[:500],
                        "metodo": "expressao_regular",
                        "confianca": confianca,
                    }
                )
    return encontrados


def _padroes():
    return (
        (TipoDadoExtraido.CPF, re.compile(r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b"), Decimal("0.700"), _cpf_valido),
        (TipoDadoExtraido.CNPJ, re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b"), Decimal("0.700"), _cnpj_valido),
        (TipoDadoExtraido.DATA, re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"), Decimal("0.600"), _data_valida),
        (
            TipoDadoExtraido.VALOR_MONETARIO,
            re.compile(r"(R\$\s?\d{1,3}(?:\.\d{3})*,\d{2})"),
            Decimal("0.650"),
            None,
        ),
        (
            TipoDadoExtraido.NUMERO_DOCUMENTO,
            re.compile(r"(?i)(?:nota fiscal|recibo|nf-e|nfe)\s*(?:n[ºo.]*)?\s*(\d{3,})"),
            Decimal("0.550"),
            None,
        ),
        (
            TipoDadoExtraido.NUMERO_PROCESSO,
            re.compile(r"(?i)processo\s*(?:n[ºo.]*)?\s*([A-Z0-9./-]*\d[A-Z0-9./-]{2,})"),
            Decimal("0.550"),
            None,
        ),
        (
            TipoDadoExtraido.NUMERO_INSTRUMENTO,
            re.compile(r"(?i)(?:termo|instrumento)\s*(?:n[ºo.]*)?\s*([A-Z0-9./-]*\d[A-Z0-9./-]{2,})"),
            Decimal("0.500"),
            None,
        ),
    )


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def _cpf_valido(valor: str) -> bool:
    numeros = _digitos(valor)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    return _digito(numeros[:9]) == numeros[9] and _digito(numeros[:10]) == numeros[10]


def _cnpj_valido(valor: str) -> bool:
    numeros = _digitos(valor)
    if len(numeros) != 14 or numeros == numeros[0] * 14:
        return False
    primeiro = _digito(numeros[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    segundo = _digito(numeros[:13], (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return primeiro == numeros[12] and segundo == numeros[13]


def _digito(base: str, pesos: tuple[int, ...] | None = None) -> str:
    if pesos is None:
        pesos = tuple(range(len(base) + 1, 1, -1))
    total = sum(int(digito) * peso for digito, peso in zip(base, pesos))
    resto = total % 11
    return "0" if resto < 2 else str(11 - resto)


def _data_valida(valor: str) -> bool:
    try:
        datetime.strptime(valor, "%d/%m/%Y")
    except ValueError:
        return False
    return True
