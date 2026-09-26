from dataclasses import dataclass
from datetime import date

from django.db.models import Q
from django.utils import timezone

from aplicacao.normas.models import Norma


@dataclass(frozen=True)
class AvaliacaoNorma:
    norma: Norma
    elegivel: bool
    motivo: str


@dataclass(frozen=True)
class ResolucaoNormativa:
    data_referencia: date
    elegiveis: list[AvaliacaoNorma]
    descartadas: list[AvaliacaoNorma]


class ResolvedorNormativo:
    """Escolhe normas por dados estruturados. Não usa modelo de linguagem nem similaridade."""

    def resolver(
        self,
        *,
        data_referencia: date,
        tipo_instrumento: str = "",
        orgao: str = "",
        tipo_prestacao: str = "",
        categoria: str = "",
        prestacao_contas=None,
    ) -> ResolucaoNormativa:
        if prestacao_contas is not None and not tipo_instrumento:
            tipo_instrumento = getattr(prestacao_contas, "tipo_instrumento", "") or ""
        elegiveis: list[AvaliacaoNorma] = []
        descartadas: list[AvaliacaoNorma] = []
        normas = Norma.objects.filter(desativada_em__isnull=True).prefetch_related("aplicabilidades")
        for norma in normas:
            motivo = self._motivo(
                norma,
                data_referencia,
                tipo_instrumento.strip(),
                orgao.strip(),
                tipo_prestacao.strip(),
                categoria.strip(),
            )
            avaliacao = AvaliacaoNorma(norma, motivo is None, motivo or self._motivo_positivo(norma, data_referencia))
            if avaliacao.elegivel:
                elegiveis.append(avaliacao)
            else:
                descartadas.append(avaliacao)
        return ResolucaoNormativa(data_referencia, elegiveis, descartadas)

    def _motivo(self, norma: Norma, data_referencia: date, tipo_instrumento: str, orgao: str, tipo_prestacao: str, categoria: str) -> str | None:
        if norma.inicio_vigencia is None:
            return "Início de vigência não informado."
        if norma.status_processamento != "disponivel":
            return "A norma ainda não está disponível para consulta."
        if data_referencia < norma.inicio_vigencia:
            return f"Fora da vigência na data {data_referencia:%d/%m/%Y}: inicia em {norma.inicio_vigencia:%d/%m/%Y}."
        if norma.fim_vigencia is not None and data_referencia > norma.fim_vigencia:
            return f"Fora da vigência na data {data_referencia:%d/%m/%Y}: encerrou em {norma.fim_vigencia:%d/%m/%Y}."
        if not self._aplicavel(norma, data_referencia, tipo_instrumento, orgao, tipo_prestacao, categoria):
            return "A aplicabilidade cadastrada não cobre o contexto informado."
        return None

    def _aplicavel(self, norma, data_referencia, tipo_instrumento, orgao, tipo_prestacao, categoria) -> bool:
        regras = list(norma.aplicabilidades.all())
        if not regras:
            return True
        return any(
            self._regra_compativel(regra, data_referencia, tipo_instrumento, orgao, tipo_prestacao, categoria)
            for regra in regras
        )

    def _regra_compativel(self, regra, data_referencia, tipo_instrumento, orgao, tipo_prestacao, categoria) -> bool:
        if not _eixo(regra.tipo_instrumento, tipo_instrumento):
            return False
        if not _eixo(regra.orgao, orgao):
            return False
        if not _eixo(regra.tipo_prestacao, tipo_prestacao):
            return False
        if not _eixo(regra.categoria, categoria):
            return False
        if regra.periodo_inicio and data_referencia < regra.periodo_inicio:
            return False
        if regra.periodo_fim and data_referencia > regra.periodo_fim:
            return False
        return True

    def _motivo_positivo(self, norma: Norma, data_referencia: date) -> str:
        fim = norma.fim_vigencia.strftime("%d/%m/%Y") if norma.fim_vigencia else "em aberto"
        return (
            f"Vigente em {data_referencia:%d/%m/%Y}: início {norma.inicio_vigencia:%d/%m/%Y}, fim {fim}. "
            "Seleção por vigência e aplicabilidade, sem similaridade."
        )


def _eixo(restricao: str, informado: str) -> bool:
    if not restricao:
        return True
    if not informado:
        return True
    return restricao.casefold() == informado.casefold()


def normas_vigentes_em(data_referencia: date):
    return Norma.objects.filter(desativada_em__isnull=True, inicio_vigencia__lte=data_referencia).filter(
        Q(fim_vigencia__isnull=True) | Q(fim_vigencia__gte=data_referencia)
    )


def hoje_local() -> date:
    return timezone.localdate()
