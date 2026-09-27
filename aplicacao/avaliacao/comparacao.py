from aplicacao.avaliacao.escolhas import AplicabilidadeComparacao
from aplicacao.avaliacao.models import ComparacaoRegra
from aplicacao.regras.escolhas import TipoExecucaoTecnica

TOKENS_DISTINTOS = {
    "não aplicável": "nao_aplicavel",
    "nao aplicavel": "nao_aplicavel",
    "não verificável": "nao_verificavel",
    "nao verificavel": "nao_verificavel",
    "não localizado": "nao_localizado",
    "nao localizado": "nao_localizado",
}


def token(resultado: str) -> str:
    return TOKENS_DISTINTOS.get((resultado or "").strip().casefold(), "")


def comparar_regras(avaliacao, execucoes, referencias) -> list[ComparacaoRegra]:
    por_regra = {item.regra_id: item for item in referencias}
    criadas = []
    for execucao in execucoes:
        referencia = por_regra.get(execucao.regra_id)
        fora = execucao.regra.tipo_execucao == TipoExecucaoTecnica.FORA_ESCOPO_V1
        if referencia is None:
            aplicabilidade = AplicabilidadeComparacao.FORA_ESCOPO if fora else AplicabilidadeComparacao.SEM_GROUND_TRUTH
            concordante = None
            motivo = "Fora do escopo." if fora else "Sem Ground Truth válido para a regra."
            resultado_gt = ""
        elif fora:
            aplicabilidade = AplicabilidadeComparacao.FORA_ESCOPO
            concordante = None
            motivo = "Fora do escopo."
            resultado_gt = referencia.resultado_esperado
        elif not referencia.aplicavel or token(referencia.resultado_esperado) == "nao_aplicavel":
            aplicabilidade = AplicabilidadeComparacao.NAO_APLICAVEL
            concordante = None
            motivo = "Não aplicável, fora do denominador."
            resultado_gt = referencia.resultado_esperado
        else:
            aplicabilidade = AplicabilidadeComparacao.AVALIAVEL
            igual = execucao.resultado_funcional.strip().casefold() == referencia.resultado_esperado.strip().casefold()
            concordante = igual
            motivo = "Concordante." if igual else "Resultados diferentes, sem normalização semântica."
            resultado_gt = referencia.resultado_esperado
        criadas.append(
            ComparacaoRegra.objects.create(
                avaliacao=avaliacao,
                regra=execucao.regra,
                execucao_regra=execucao,
                ground_truth_regra=referencia,
                versao_regra=execucao.regra.versao,
                resultado_sistema=execucao.resultado_funcional,
                resultado_ground_truth=resultado_gt,
                aplicabilidade=aplicabilidade,
                concordante=concordante,
                motivo=motivo,
            )
        )
    return criadas


def resumir_regras(comparacoes) -> dict:
    grupos = {
        "concordantes": 0,
        "divergentes": 0,
        "nao_aplicaveis": 0,
        "nao_verificaveis": 0,
        "nao_localizadas": 0,
        "sem_ground_truth": 0,
        "fora_escopo": 0,
        "avaliaveis": 0,
    }
    por_categoria: dict[str, dict] = {}
    por_executor: dict[str, dict] = {}
    for item in comparacoes:
        categoria = item.regra.categoria or "Sem categoria"
        executor = item.regra.tipo_execucao
        por_categoria.setdefault(categoria, {"concordantes": 0, "avaliaveis": 0, "concordancia": None})
        por_executor.setdefault(executor, {"concordantes": 0, "avaliaveis": 0, "concordancia": None})
        if item.aplicabilidade == AplicabilidadeComparacao.SEM_GROUND_TRUTH:
            grupos["sem_ground_truth"] += 1
            continue
        if item.aplicabilidade == AplicabilidadeComparacao.FORA_ESCOPO:
            grupos["fora_escopo"] += 1
            continue
        if item.aplicabilidade == AplicabilidadeComparacao.NAO_APLICAVEL:
            grupos["nao_aplicaveis"] += 1
            continue
        grupos["avaliaveis"] += 1
        por_categoria[categoria]["avaliaveis"] += 1
        por_executor[executor]["avaliaveis"] += 1
        if item.concordante:
            grupos["concordantes"] += 1
            por_categoria[categoria]["concordantes"] += 1
            por_executor[executor]["concordantes"] += 1
        else:
            grupos["divergentes"] += 1
        marca = token(item.resultado_ground_truth)
        if marca == "nao_verificavel":
            grupos["nao_verificaveis"] += 1
        elif marca == "nao_localizado":
            grupos["nao_localizadas"] += 1
    from decimal import Decimal, ROUND_HALF_UP

    def taxa(parte, todo):
        if todo == 0:
            return None
        return format((Decimal(parte) / Decimal(todo)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")

    grupos["concordancia"] = taxa(grupos["concordantes"], grupos["avaliaveis"])
    for bloco in (por_categoria, por_executor):
        for item in bloco.values():
            item["concordancia"] = taxa(item["concordantes"], item["avaliaveis"])
    return {"totais": grupos, "por_categoria": por_categoria, "por_executor": por_executor}
