from datetime import date

from django.db.models import Count

from aplicacao.normas.escolhas import StatusProcessamentoNorma
from aplicacao.normas.models import Norma, TrechoNormativo
from aplicacao.normas.resolvedor import hoje_local, normas_vigentes_em


def indicadores_normativos(quando: date | None = None) -> dict[str, int]:
    referencia = quando or hoje_local()
    ativas = Norma.objects.filter(desativada_em__isnull=True)
    contagens = {
        "Normas cadastradas": ativas.count(),
        "Normas vigentes": normas_vigentes_em(referencia).count(),
        "Normas processadas": ativas.filter(status_processamento=StatusProcessamentoNorma.DISPONIVEL).count(),
        "Trechos indexados": TrechoNormativo.objects.filter(
            embedding__isnull=False,
            norma__desativada_em__isnull=True,
        ).count(),
        "Normas com erro": ativas.filter(status_processamento=StatusProcessamentoNorma.ERRO).count(),
    }
    return contagens


def contagem_por_situacao() -> dict[str, int]:
    return dict(Norma.objects.filter(desativada_em__isnull=True).values_list("situacao").annotate(total=Count("id")).order_by())
