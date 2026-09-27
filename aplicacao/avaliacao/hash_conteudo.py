import hashlib
import json
from decimal import Decimal


def _dumps(conteudo: dict) -> str:
    return json.dumps(conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_padrao)


def _padrao(valor):
    if isinstance(valor, Decimal):
        return format(valor, "f")
    raise TypeError(f"Valor não serializável: {type(valor)}")


def _sha(conteudo: dict) -> str:
    return hashlib.sha256(_dumps(conteudo).encode("utf-8")).hexdigest()


def conteudo_ground_truth(ground_truth) -> dict:
    regras = []
    for item in ground_truth.regras_referencia.select_related("regra").order_by("regra__codigo", "id"):
        regras.append(
            {
                "aplicavel": item.aplicavel,
                "justificativa": item.justificativa,
                "regra": item.regra.codigo,
                "resultado_esperado": item.resultado_esperado,
                "versao": item.regra.versao,
            }
        )
    achados = []
    for item in ground_truth.achados_referencia.order_by("codigo", "id"):
        achados.append(
            {
                "categoria": item.categoria,
                "codigo": item.codigo,
                "criticidade": item.criticidade,
                "descricao": item.descricao,
                "evidencias": list(item.evidencias.order_by("codigo").values_list("codigo", flat=True)),
                "fato": item.fato,
                "materialidade": None if item.materialidade is None else format(item.materialidade, "f"),
                "normas": list(item.normas.order_by("id").values_list("id", flat=True)),
                "prioridade": item.prioridade,
                "regras": list(item.regras.order_by("codigo", "versao").values_list("codigo", flat=True)),
                "situacao": item.situacao,
                "titulo": item.titulo,
                "trechos": list(item.trechos.order_by("id").values_list("id", flat=True)),
            }
        )
    return {
        "achados": achados,
        "codigo": ground_truth.codigo,
        "modo": ground_truth.modo,
        "regras": regras,
        "versao": ground_truth.versao,
    }


def calcular_hash_ground_truth(ground_truth) -> str:
    return _sha(conteudo_ground_truth(ground_truth))


def conteudo_snapshot(snapshot) -> dict:
    return {
        "congelamento_pre_analise": snapshot.congelamento_pre_analise.isoformat() if snapshot.congelamento_pre_analise else "",
        "execucao_analise": snapshot.execucao_analise_id,
        "hash_pre_analise": snapshot.hash_pre_analise,
        "pre_analise": snapshot.pre_analise_id,
        "prestacao": snapshot.prestacao_contas_id,
        "referencias": snapshot.referencias,
        "versao_pre_analise": snapshot.versao_pre_analise,
    }


def calcular_hash_snapshot(snapshot) -> str:
    return _sha(conteudo_snapshot(snapshot))


def conteudo_avaliacao(avaliacao) -> dict:
    correspondencias = []
    for item in avaliacao.correspondencias.order_by("id"):
        correspondencias.append(
            {
                "achado": item.achado_id,
                "classificacao": item.classificacao,
                "ground_truth_achado": item.ground_truth_achado_id,
                "metodo": item.metodo,
            }
        )
    comparacoes = []
    for item in avaliacao.comparacoes_regra.order_by("regra_id", "id"):
        comparacoes.append(
            {
                "aplicabilidade": item.aplicabilidade,
                "concordante": item.concordante,
                "regra": item.regra_id,
                "resultado_ground_truth": item.resultado_ground_truth,
                "resultado_sistema": item.resultado_sistema,
            }
        )
    return {
        "codigo": avaliacao.codigo,
        "comparacoes": comparacoes,
        "correspondencias": correspondencias,
        "ground_truth": avaliacao.ground_truth_id,
        "metricas": avaliacao.metricas,
        "snapshot": avaliacao.snapshot.hash_conteudo if avaliacao.snapshot_id else "",
        "versao": avaliacao.versao,
    }


def calcular_hash_avaliacao(avaliacao) -> str:
    return _sha(conteudo_avaliacao(avaliacao))
