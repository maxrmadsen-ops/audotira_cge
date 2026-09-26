import hashlib
import math
import re
import unicodedata
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def normalizar_texto(texto: str) -> str:
    """Trata o conteúdo como dado. Não interpreta instruções encontradas no texto."""
    limpo = (texto or "").replace("\x00", "")
    limpo = unicodedata.normalize("NFKC", limpo)
    limpo = limpo.lower()
    limpo = re.sub(r"[ \t]+", " ", limpo)
    limpo = re.sub(r"\n{3,}", "\n\n", limpo)
    return limpo.strip()


def hash_conteudo(texto_normalizado: str) -> str:
    return hashlib.sha256(texto_normalizado.encode("utf-8")).hexdigest()


class ProvedorEmbeddings(Protocol):
    nome: str
    modelo: str
    dimensao: int

    def incorporar(self, textos: list[str]) -> list[list[float]]:
        ...


class ProvedorSimulado:
    """Vetor determinístico a partir dos termos. Não acessa a rede."""

    nome = "simulado"

    def __init__(self, modelo: str, dimensao: int):
        self.modelo = modelo
        self.dimensao = dimensao

    def incorporar(self, textos: list[str]) -> list[list[float]]:
        return [self._vetor(texto) for texto in textos]

    def _vetor(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dimensao
        termos = re.findall(r"\w+", normalizar_texto(texto), flags=re.UNICODE)
        for termo in termos:
            indice = int(hashlib.sha256(termo.encode("utf-8")).hexdigest(), 16) % self.dimensao
            vetor[indice] += 1.0
        norma = math.sqrt(sum(valor * valor for valor in vetor)) or 1.0
        return [valor / norma for valor in vetor]


class GerenciadorEmbeddings:
    def __init__(self, provedor: ProvedorEmbeddings | None = None):
        self.provedor = provedor or obter_provedor()

    def incorporar(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        vetores = self.provedor.incorporar(textos)
        if any(len(vetor) != self.provedor.dimensao for vetor in vetores):
            raise ImproperlyConfigured("O provedor devolveu um vetor com dimensão diferente da configurada.")
        return vetores


def obter_provedor() -> ProvedorEmbeddings:
    nome = settings.EMBEDDING_PROVEDOR
    if nome == "simulado":
        return ProvedorSimulado(modelo=settings.EMBEDDING_MODELO, dimensao=settings.EMBEDDING_DIMENSAO)
    raise ImproperlyConfigured("O provedor de embeddings configurado não está disponível nesta onda.")
