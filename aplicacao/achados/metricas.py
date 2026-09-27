from decimal import Decimal

from django.db.models import Sum

from aplicacao.achados.escolhas import Criticidade, OrigemGeracao, Prioridade, StatusAchado, TipoConstatacao
from aplicacao.achados.models import Achado, Evidencia, RevisaoAchado, Sinalizacao
from aplicacao.regras.models import ExecucaoRegra, RegraAnalise


def indicadores_gerais() -> dict:
    achados = Achado.objects.all()
    base = _indicadores(achados)
    base["quantidade_evidencias"] = Evidencia.objects.count()
    return base


def da_prestacao(prestacao) -> dict:
    achados = Achado.objects.filter(prestacao_contas=prestacao)
    base = _indicadores(achados)
    base["quantidade_evidencias"] = Evidencia.objects.filter(prestacao_contas=prestacao).count()
    analises = prestacao.execucoes_analise.count()
    execucoes = ExecucaoRegra.objects.filter(analise__prestacao_contas=prestacao)
    base.update(
        {
            "total_regras": RegraAnalise.objects.filter(ativa=True).count(),
            "regras_executadas": execucoes.exclude(resultado_funcional="").count(),
            "sinalizacoes": Sinalizacao.objects.filter(analise__prestacao_contas=prestacao).count(),
            "analises": analises,
            "aguardando_revisao": achados.filter(status__in=[StatusAchado.POTENCIAL, StatusAchado.EM_REVISAO]).count(),
            "achados_lista": achados.select_related("prestacao_contas"),
        }
    )
    return base


def _indicadores(achados) -> dict:
    materialidade = achados.filter(tipo_constatacao=TipoConstatacao.ACHADO_POTENCIAL).aggregate(total=Sum("materialidade_financeira"))["total"]
    confirmados = achados.filter(status=StatusAchado.CONFIRMADO).count()
    potenciais = achados.filter(status=StatusAchado.POTENCIAL).count()
    revisados = RevisaoAchado.objects.filter(achado__in=achados).count()
    return {
        "achados_potenciais": potenciais,
        "em_revisao": achados.filter(status=StatusAchado.EM_REVISAO).count(),
        "achados_confirmados": confirmados,
        "achados_descartados": achados.filter(status=StatusAchado.DESCARTADO).count(),
        "achados_diligencia": achados.filter(status=StatusAchado.NECESSITA_DILIGENCIA).count(),
        "alta_prioridade": achados.filter(prioridade__in=[Prioridade.ALTA, Prioridade.URGENTE]).count(),
        "materialidade_potencial": materialidade if materialidade is not None else Decimal("0.00"),
        "constatacoes_positivas": achados.filter(tipo_constatacao=TipoConstatacao.CONSTATACAO_POSITIVA).count(),
        "achados_origem_deterministica": achados.filter(origem_geracao=OrigemGeracao.DETERMINISTICA).count(),
        "achados_origem_ia": achados.filter(origem_geracao=OrigemGeracao.IA).count(),
        "criticidade_alta": achados.filter(criticidade__in=[Criticidade.ALTA, Criticidade.CRITICA]).count(),
        "revisoes": revisados,
        "taxa_confirmacao": (Decimal(confirmados) / Decimal(achados.count())).quantize(Decimal("0.0001")) if achados.count() else Decimal("0"),
    }
