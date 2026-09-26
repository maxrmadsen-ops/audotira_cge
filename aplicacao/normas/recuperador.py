from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from pgvector.django import CosineDistance

from aplicacao.normas.embeddings import GerenciadorEmbeddings
from aplicacao.normas.escolhas import MetodoRecuperacao
from aplicacao.normas.models import ConsultaNormativa, ResultadoConsultaNormativa, TrechoNormativo
from aplicacao.normas.resolvedor import ResolvedorNormativo


class RecuperadorNormativo:
    def __init__(self, resolvedor: ResolvedorNormativo | None = None, embeddings: GerenciadorEmbeddings | None = None):
        self.resolvedor = resolvedor or ResolvedorNormativo()
        self.embeddings = embeddings or GerenciadorEmbeddings()

    def recuperar(
        self,
        *,
        texto: str,
        data_referencia,
        tipo_instrumento: str = "",
        orgao: str = "",
        tipo_prestacao: str = "",
        categoria: str = "",
        prestacao_contas=None,
        usuario=None,
    ) -> ConsultaNormativa:
        resolucao = self.resolvedor.resolver(
            data_referencia=data_referencia,
            tipo_instrumento=tipo_instrumento,
            orgao=orgao,
            tipo_prestacao=tipo_prestacao,
            categoria=categoria,
            prestacao_contas=prestacao_contas,
        )
        ids = [item.norma.id for item in resolucao.elegiveis]
        combinados = self._combinar(texto, ids) if ids else {}
        consulta = ConsultaNormativa.objects.create(
            texto=texto,
            data_referencia=data_referencia,
            tipo_instrumento=tipo_instrumento,
            orgao=orgao,
            tipo_prestacao=tipo_prestacao,
            categoria=categoria,
            prestacao_contas=prestacao_contas,
            usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
            filtros={
                "data_referencia": data_referencia.isoformat(),
                "tipo_instrumento": tipo_instrumento,
                "orgao": orgao,
                "tipo_prestacao": tipo_prestacao,
                "categoria": categoria,
                "prestacao_id": getattr(prestacao_contas, "id", None),
                "ids_elegiveis": ids,
            },
            normas_consideradas=[_resumo(item) for item in (*resolucao.elegiveis, *resolucao.descartadas)],
        )
        ordenados = sorted(combinados.values(), key=lambda item: item["score_final"], reverse=True)
        limite = int(settings.NORMATIVO_LIMITE_RESULTADOS)
        for ordem, item in enumerate(ordenados[:limite], start=1):
            if item["score_final"] <= 0:
                continue
            ResultadoConsultaNormativa.objects.create(
                consulta=consulta,
                trecho_id=item["trecho_id"],
                ordem=ordem,
                score_lexical=item["score_lexical"],
                score_vetorial=item["score_vetorial"],
                score_final=item["score_final"],
                metodo=item["metodo"],
            )
        return consulta

    def _combinar(self, texto: str, ids: list[int]) -> dict[int, dict]:
        lexicais = _busca_lexical(texto, ids)
        vetoriais = _busca_vetorial(texto, ids, self.embeddings)
        peso_lexical = float(settings.NORMATIVO_PESO_LEXICAL)
        peso_vetorial = float(settings.NORMATIVO_PESO_VETORIAL)
        chaves = set(lexicais) | set(vetoriais)
        combinados = {}
        for trecho_id in chaves:
            lexical = lexicais.get(trecho_id)
            vetorial = vetoriais.get(trecho_id)
            score_lexical = lexical or 0.0
            score_vetorial = vetorial or 0.0
            score_final = (peso_lexical * score_lexical) + (peso_vetorial * score_vetorial)
            if score_lexical and score_vetorial:
                metodo = MetodoRecuperacao.HIBRIDO
            elif score_vetorial:
                metodo = MetodoRecuperacao.VETORIAL
            else:
                metodo = MetodoRecuperacao.LEXICAL
            combinados[trecho_id] = {
                "trecho_id": trecho_id,
                "score_lexical": lexical,
                "score_vetorial": vetorial,
                "score_final": score_final,
                "metodo": metodo,
            }
        return combinados


def _busca_lexical(texto: str, ids: list[int]) -> dict[int, float]:
    if not ids or not texto.strip():
        return {}
    vetor = SearchVector("texto_normalizado", config="portuguese")
    consulta = SearchQuery(texto, config="portuguese", search_type="websearch")
    encontrados = (
        TrechoNormativo.objects.filter(norma_id__in=ids)
        .annotate(rank=SearchRank(vetor, consulta))
        .filter(rank__gt=0)
        .order_by("-rank")
    )
    bruto = {item.id: float(item.rank) for item in encontrados}
    if not bruto:
        return {}
    maior = max(bruto.values()) or 1.0
    return {chave: valor / maior for chave, valor in bruto.items()}


def _busca_vetorial(texto: str, ids: list[int], embeddings: GerenciadorEmbeddings) -> dict[int, float]:
    if not ids or not texto.strip():
        return {}
    vetor = embeddings.incorporar([texto])[0]
    encontrados = (
        TrechoNormativo.objects.filter(norma_id__in=ids, embedding__isnull=False)
        .annotate(distancia=CosineDistance("embedding", vetor))
        .order_by("distancia")
    )
    return {item.id: max(0.0, 1.0 - float(item.distancia)) for item in encontrados}


def _resumo(item) -> dict:
    norma = item.norma
    return {
        "id": norma.id,
        "numero": norma.numero,
        "ano": norma.ano,
        "titulo": norma.titulo,
        "elegivel": item.elegivel,
        "motivo": item.motivo,
        "inicio_vigencia": norma.inicio_vigencia.isoformat() if norma.inicio_vigencia else "",
        "fim_vigencia": norma.fim_vigencia.isoformat() if norma.fim_vigencia else "",
    }
