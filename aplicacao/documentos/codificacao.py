"""Recupera texto de PDFs cuja fonte mapeia letras para a área de uso privado."""


def mapear_uso_privado(texto: str) -> str:
    return "".join(
        chr(ord(caractere) - 0xF000) if 0xF000 <= ord(caractere) <= 0xF0FF else caractere
        for caractere in (texto or "")
    )


def decodificar_uso_privado(texto: str) -> tuple[str, bool]:
    """Devolve o texto legível e se a camada nativa precisou desse ajuste.

    Alguns relatórios desenham cada letra no intervalo U+F000–U+F0FF.
    A qualidade textual só é avaliada depois deste ajuste, para não disparar
    OCR quando a página já tem texto recuperável.
    """

    bruto = texto or ""
    if not bruto:
        return bruto, False
    privados = sum(1 for caractere in bruto if 0xF000 <= ord(caractere) <= 0xF0FF)
    if privados < 12 or privados / len(bruto) < 0.25:
        return bruto, False
    decodificado = mapear_uso_privado(bruto)
    return decodificado, True
