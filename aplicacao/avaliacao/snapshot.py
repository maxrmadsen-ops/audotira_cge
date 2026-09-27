from aplicacao.avaliacao.excecoes import ErroAvaliacao
from aplicacao.avaliacao.hash_conteudo import calcular_hash_snapshot
from aplicacao.avaliacao.models import SnapshotAvaliacao
from aplicacao.pareceres.escolhas import StatusPreAnalise


def criar_snapshot(pre_analise) -> SnapshotAvaliacao:
    if pre_analise.status != StatusPreAnalise.CONGELADA:
        raise ErroAvaliacao("A avaliação oficial exige pré-análise congelada.")
    analise = pre_analise.execucao_analise
    achados = list(analise.achados.order_by("id"))
    execucoes = list(analise.execucoes.select_related("regra").order_by("ordem", "id"))
    evidencias = []
    normas = []
    for achado in achados:
        evidencias.extend(achado.vinculos_evidencia.values_list("evidencia_id", flat=True))
        for fundamento in achado.fundamentacoes.select_related("norma"):
            normas.append({"id": fundamento.norma_id, "versao": fundamento.norma.versao})
    referencias = {
        "regras": [{"id": item.regra_id, "codigo": item.regra.codigo, "versao": item.regra.versao} for item in execucoes],
        "achados": [item.pk for item in achados],
        "evidencias": sorted(set(evidencias)),
        "normas": normas,
        "prompt": {"id": pre_analise.versao_prompt_id, "versao": getattr(pre_analise.versao_prompt, "versao", None)},
        "modelo": {"provedor": pre_analise.provedor, "id": pre_analise.modelo_inteligencia_artificial_id},
    }
    snapshot = SnapshotAvaliacao(
        prestacao_contas=pre_analise.prestacao_contas,
        execucao_analise=analise,
        pre_analise=pre_analise,
        versao_pre_analise=pre_analise.versao,
        hash_pre_analise=pre_analise.hash_conteudo,
        congelamento_pre_analise=pre_analise.congelada_em,
        referencias=referencias,
    )
    snapshot.hash_conteudo = calcular_hash_snapshot(snapshot)
    snapshot.save()
    return snapshot
