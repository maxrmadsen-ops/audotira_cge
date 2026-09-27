import re
import unicodedata

from aplicacao.achados.escolhas import EXPRESSOES_CONCLUSIVAS_VEDADAS


def _normalizar(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFKD", texto or "")
    return "".join(caractere for caractere in decomposicao if not unicodedata.combining(caractere)).upper()


def expressao_vedada(texto: str) -> str:
    normalizado = _normalizar(texto)
    for expressao in EXPRESSOES_CONCLUSIVAS_VEDADAS:
        if _normalizar(expressao) in normalizado:
            return expressao
    return ""


def texto_permitido(texto: str, citacoes: list[str] | None = None) -> str:
    """Afasta acusação automática. Citação literal de fonte permitida permanece."""

    bruto = " ".join((texto or "").split())
    if not bruto:
        return ""
    termo = expressao_vedada(bruto)
    if not termo:
        return bruto[:2000]
    citacoes_normais = [_normalizar(item) for item in (citacoes or []) if item]
    if any(_normalizar(termo) in citacao for citacao in citacoes_normais):
        return bruto[:2000]
    return re.sub(
        re.escape(termo),
        "possível inconsistência",
        bruto,
        count=1,
        flags=re.IGNORECASE,
    )[:2000]
