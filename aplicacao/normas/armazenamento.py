import uuid
from pathlib import Path

from django.conf import settings

from aplicacao.documentos.armazenamento import ErroArmazenamento


def caminho_seguro(relativo: str) -> Path:
    if not relativo or "\x00" in relativo:
        raise ErroArmazenamento("Caminho de armazenamento inválido.")
    raiz = Path(settings.NORMAS_RAIZ).resolve()
    candidato = Path(relativo)
    if candidato.is_absolute() or ".." in candidato.parts:
        raise ErroArmazenamento("Caminho de armazenamento inválido.")
    destino = (raiz / candidato).resolve()
    if not destino.is_relative_to(raiz):
        raise ErroArmazenamento("Caminho de armazenamento inválido.")
    return destino


def armazenar_pdf(norma_id: int, conteudo: bytes) -> str:
    relativo = f"{int(norma_id)}/{uuid.uuid4().hex}.pdf"
    destino = caminho_seguro(relativo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    return relativo


def ler_arquivo(relativo: str) -> Path:
    destino = caminho_seguro(relativo)
    if not destino.is_file():
        raise ErroArmazenamento("Arquivo não encontrado no armazenamento protegido.")
    return destino
