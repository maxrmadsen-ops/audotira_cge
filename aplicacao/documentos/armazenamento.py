import uuid
from pathlib import Path

from django.conf import settings


class ErroArmazenamento(Exception):
    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)


def caminho_seguro(relativo: str) -> Path:
    """Resolve um caminho interno e recusa saída da raiz de documentos."""
    if not relativo or "\x00" in relativo:
        raise ErroArmazenamento("Caminho de armazenamento inválido.")
    raiz = Path(settings.DOCUMENTOS_RAIZ).resolve()
    candidato = Path(relativo)
    if candidato.is_absolute() or ".." in candidato.parts:
        raise ErroArmazenamento("Caminho de armazenamento inválido.")
    destino = (raiz / candidato).resolve()
    if not destino.is_relative_to(raiz):
        raise ErroArmazenamento("Caminho de armazenamento inválido.")
    return destino


def armazenar_pdf(prestacao_id: int, conteudo: bytes) -> str:
    relativo = f"{int(prestacao_id)}/{uuid.uuid4().hex}.pdf"
    destino = caminho_seguro(relativo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    return relativo


def ler_arquivo(relativo: str) -> Path:
    destino = caminho_seguro(relativo)
    if not destino.is_file():
        raise ErroArmazenamento("Arquivo não encontrado no armazenamento protegido.")
    return destino


def remover_arquivo(relativo: str) -> None:
    try:
        caminho_seguro(relativo).unlink(missing_ok=True)
    except ErroArmazenamento:
        return
