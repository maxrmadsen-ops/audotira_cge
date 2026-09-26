import hashlib
from pathlib import Path

from django.conf import settings


class ErroValidacaoDocumento(Exception):
    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)


def validar_envio(nome_original: str, conteudo: bytes, tipo_informado: str = "") -> dict:
    """Valida o arquivo pelo conteúdo, não apenas pela extensão enviada."""
    if not conteudo:
        raise ErroValidacaoDocumento("O arquivo está vazio.")
    limite = int(settings.DOCUMENTO_TAMANHO_MAXIMO_BYTES)
    if len(conteudo) > limite:
        raise ErroValidacaoDocumento("O arquivo excede o tamanho máximo permitido.")
    extensao = Path(nome_original or "").suffix.lower().lstrip(".")
    permitidas = {item.lower() for item in settings.DOCUMENTO_EXTENSOES_PERMITIDAS}
    if extensao not in permitidas:
        raise ErroValidacaoDocumento("A extensão não é permitida. Envie um PDF.")
    if not conteudo.startswith(b"%PDF"):
        raise ErroValidacaoDocumento("O conteúdo não é um PDF válido.")
    if tipo_informado and tipo_informado not in {"application/pdf", "application/x-pdf", ""}:
        raise ErroValidacaoDocumento("O tipo informado pelo navegador não corresponde a um PDF.")
    return {
        "extensao": extensao,
        "mime_type": "application/pdf",
        "tamanho_bytes": len(conteudo),
        "hash_sha256": hashlib.sha256(conteudo).hexdigest(),
    }
