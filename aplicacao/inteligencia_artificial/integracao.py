from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from aplicacao.inteligencia_artificial.agentes import classe_do_agente
from aplicacao.inteligencia_artificial.escolhas import StatusUso
from aplicacao.inteligencia_artificial.models import UsoInteligenciaArtificial
from aplicacao.regras.escolhas import Encaminhamento, StatusTecnico
from aplicacao.regras.resultados import ResultadoExecutor, referencia, status_de


def executar_semantica(regra, contexto_execucao, referencias, entradas_base) -> ResultadoExecutor:
    agente = classe_do_agente(regra.codigo)()
    chamada = agente.executar(regra, contexto_execucao, analise=getattr(contexto_execucao, "analise", None))
    if chamada is None:
        return ResultadoExecutor(
            "REQUER ANÁLISE SEMÂNTICA",
            StatusTecnico.NAO_EXECUTADA,
            "A integração de IA está desligada ou o catálogo de prompts não foi carregado.",
            referencias=referencias,
            entradas=entradas_base,
            encaminhamento=Encaminhamento.REQUER_IA,
        )
    resposta = chamada.resposta or {}
    ia = {
        "agente": agente.codigo,
        "provedor": chamada.provedor,
        "modelo": chamada.modelo,
        "versao_prompt": chamada.usos[-1].versao_prompt_id if chamada.usos else None,
        "resultado": resposta.get("resultado", ""),
        "justificativa": resposta.get("justificativa_resumida", ""),
        "fontes": resposta.get("fontes_utilizadas") or [],
        "fontes_rejeitadas": resposta.get("fontes_rejeitadas") or [],
        "fundamentos": resposta.get("fundamentos_normativos") or [],
        "limitacoes": resposta.get("limitacoes") or [],
        "revisao_humana": True,
        "tokens_entrada": sum(uso.tokens_entrada for uso in chamada.usos),
        "tokens_saida": sum(uso.tokens_saida for uso in chamada.usos),
        "latencia_ms": sum(uso.duracao_ms for uso in chamada.usos),
        "custo_estimado_total": _texto_custo(chamada.usos),
        "fallback_utilizado": chamada.fallback_utilizado,
        "status": chamada.status,
        "uso_id": chamada.usos[-1].pk if chamada.usos else None,
    }
    entradas = dict(entradas_base)
    entradas["resultado_pre_ia"] = "REQUER ANÁLISE SEMÂNTICA"
    entradas["ia"] = ia
    entradas["usos"] = [uso.pk for uso in chamada.usos]
    fontes = list(referencias)
    for fonte in ia["fontes"]:
        if not isinstance(fonte, dict):
            continue
        fontes.append(
            referencia(
                tipo_fonte=str(fonte.get("tipo") or "documento")[:40],
                identificador=fonte.get("identificador"),
                campo="pagina",
                valor_utilizado=fonte.get("pagina") or "",
                papel_na_regra="fonte_ia_validada",
            )
        )
    status = StatusTecnico.ERRO if chamada.status == StatusUso.ERRO_CONTROLADO else status_de(resposta.get("resultado") or "INCONCLUSIVO")
    if chamada.status == StatusUso.LIMITE_EXCEDIDO:
        status = StatusTecnico.INCONCLUSIVO
    return ResultadoExecutor(
        (resposta.get("resultado") or "INCONCLUSIVO")[:120],
        status,
        " ".join(ia["limitacoes"])[:1000],
        referencias=fontes,
        entradas=entradas,
        encaminhamento=Encaminhamento.REQUER_IA,
    )


def vincular_usos(execucao, usos: list[int]) -> None:
    if not usos:
        return
    UsoInteligenciaArtificial.objects.filter(pk__in=usos).update(
        execucao_regra=execucao,
        execucao_analise=execucao.analise,
    )


def _texto_custo(usos) -> str:
    total = Decimal("0")
    houve = False
    for uso in usos:
        if uso.custo_estimado_total is not None:
            total += uso.custo_estimado_total
            houve = True
    if not houve:
        return ""
    return f"{total:.6f}"


def resumo_consumo():
    hoje = timezone.localdate()
    base = UsoInteligenciaArtificial.objects.all()
    dia = base.filter(iniciada_em__date=hoje)

    def agregar(consulta, campo):
        return list(
            consulta.values(campo)
            .annotate(
                chamadas=Count("id"),
                tokens=Coalesce(Sum("tokens_total"), 0),
                custo=Coalesce(Sum("custo_estimado_total"), Decimal("0")),
            )
            .order_by(campo)
        )

    return {
        "hoje": dia.aggregate(
            chamadas=Count("id"),
            tokens=Coalesce(Sum("tokens_total"), 0),
            custo=Coalesce(Sum("custo_estimado_total"), Decimal("0")),
        ),
        "por_provedor": agregar(base, "provedor"),
        "por_modelo": agregar(base, "identificador_modelo"),
        "por_agente": agregar(base, "agente"),
        "por_prestacao": agregar(base.exclude(prestacao_contas__isnull=True), "prestacao_contas_id"),
        "por_regra": agregar(base.exclude(regra__isnull=True), "regra__codigo"),
    }
