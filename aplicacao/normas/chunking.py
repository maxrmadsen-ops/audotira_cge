from django.conf import settings

from aplicacao.normas.embeddings import hash_conteudo, normalizar_texto
from aplicacao.normas.escolhas import MetodoSegmentacao


def gerar_chunks(blocos: list[dict]) -> list[dict]:
    limite = int(settings.NORMATIVO_CHUNK_MAXIMO)
    sobreposicao = int(settings.NORMATIVO_CHUNK_SOBREPOSICAO)
    chunks: list[dict] = []
    for bloco in blocos:
        texto = "\n".join(linha for linha in bloco.get("linhas", []) if linha).strip()
        if not texto:
            continue
        metodo = (
            MetodoSegmentacao.ESTRUTURA_JURIDICA
            if bloco.get("estruturado")
            else MetodoSegmentacao.JANELA_TEXTUAL
        )
        partes = [texto] if len(texto) <= limite else _partir(texto, limite, sobreposicao)
        for parte in partes:
            normalizado = normalizar_texto(parte)
            chunks.append(
                {
                    "artigo": bloco.get("artigo") or "",
                    "paragrafo": bloco.get("paragrafo") or "",
                    "inciso": bloco.get("inciso") or "",
                    "alinea": bloco.get("alinea") or "",
                    "secao": bloco.get("secao") or "",
                    "titulo_secao": bloco.get("titulo_secao") or "",
                    "pagina_inicio": bloco.get("pagina_inicio"),
                    "pagina_fim": bloco.get("pagina_fim"),
                    "texto": parte,
                    "texto_normalizado": normalizado,
                    "hash_conteudo": hash_conteudo(normalizado),
                    "metodo_segmentacao": metodo,
                    "metadados": bloco.get("metadados") or {},
                }
            )
    for ordem, chunk in enumerate(chunks, start=1):
        chunk["ordem"] = ordem
    return chunks


def _partir(texto: str, limite: int, sobreposicao: int) -> list[str]:
    if sobreposicao >= limite:
        sobreposicao = max(0, limite // 5)
    partes = []
    inicio = 0
    while inicio < len(texto):
        fim = min(len(texto), inicio + limite)
        partes.append(texto[inicio:fim].strip())
        if fim >= len(texto):
            break
        inicio = max(0, fim - sobreposicao)
    return [parte for parte in partes if parte]
