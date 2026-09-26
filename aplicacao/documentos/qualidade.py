import re

from django.conf import settings

from aplicacao.documentos.escolhas import QualidadeExtracao


def avaliar_qualidade(texto: str) -> tuple[str, bool]:
    """Decide se a camada textual da página é utilizável. OCR só entra se não for."""
    limpo = (texto or "").strip()
    if not limpo:
        return QualidadeExtracao.AUSENTE, True
    caracteres = len(re.sub(r"\s+", "", limpo))
    palavras = re.findall(r"[0-9A-Za-zÀ-ÿ]{2,}", limpo)
    if caracteres < int(settings.OCR_MINIMO_CARACTERES) or len(palavras) < int(settings.OCR_MINIMO_PALAVRAS):
        return QualidadeExtracao.INSUFICIENTE, True
    uteis = sum(1 for caractere in limpo if caractere.isalnum() or caractere.isspace())
    if uteis / len(limpo) < float(settings.OCR_LIMIAR_LEGIBILIDADE):
        return QualidadeExtracao.ILEGIVEL, True
    return QualidadeExtracao.SUFICIENTE, False
