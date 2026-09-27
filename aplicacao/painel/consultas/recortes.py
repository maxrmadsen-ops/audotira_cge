"""Recortes compartilhados. O período usa a data de criação ou de início do evento."""

from __future__ import annotations

from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncMonth

from aplicacao.painel.consultas.filtros import FiltrosPainel


def _periodo(qs: QuerySet, filtros: FiltrosPainel, campo: str) -> QuerySet:
    if filtros.inicio:
        qs = qs.filter(**{f"{campo}__date__gte": filtros.inicio})
    if filtros.fim:
        qs = qs.filter(**{f"{campo}__date__lte": filtros.fim})
    return qs


def _origem(qs: QuerySet, filtros: FiltrosPainel, campo: str = "demonstracao") -> QuerySet:
    if filtros.origem == "demonstracao":
        return qs.filter(**{campo: True})
    if filtros.origem == "operacional":
        return qs.filter(**{campo: False})
    return qs


def prestacoes(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.prestacoes_contas.models import PrestacaoContas

    qs = PrestacaoContas.objects.all()
    qs = _periodo(qs, filtros, "criado_em")
    qs = _origem(qs, filtros)
    if filtros.prestacao:
        qs = qs.filter(pk=filtros.prestacao)
    if filtros.situacao:
        qs = qs.filter(situacao=filtros.situacao)
    if filtros.concedente:
        qs = qs.filter(concedente_id=filtros.concedente)
    if filtros.beneficiario:
        qs = qs.filter(beneficiario_id=filtros.beneficiario)
    if filtros.tipo_instrumento:
        qs = qs.filter(instrumentos__tipo=filtros.tipo_instrumento).distinct()
    if filtros.responsavel:
        qs = qs.filter(criado_por_id=filtros.responsavel)
    return qs


def _por_prestacao(qs: QuerySet, filtros: FiltrosPainel, relacao: str = "prestacao_contas") -> QuerySet:
    if filtros.prestacao:
        qs = qs.filter(**{f"{relacao}_id": filtros.prestacao})
    if filtros.situacao:
        qs = qs.filter(**{f"{relacao}__situacao": filtros.situacao})
    if filtros.concedente:
        qs = qs.filter(**{f"{relacao}__concedente_id": filtros.concedente})
    if filtros.beneficiario:
        qs = qs.filter(**{f"{relacao}__beneficiario_id": filtros.beneficiario})
    if filtros.tipo_instrumento:
        qs = qs.filter(**{f"{relacao}__instrumentos__tipo": filtros.tipo_instrumento}).distinct()
    return qs


def documentos(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.documentos.models import Documento

    qs = Documento.objects.ativos()
    qs = _periodo(qs, filtros, "criado_em")
    qs = _origem(qs, filtros)
    qs = _por_prestacao(qs, filtros)
    if filtros.tipo_documento:
        qs = qs.filter(tipo_documento=filtros.tipo_documento)
    if filtros.situacao:
        qs = qs.filter(status_processamento=filtros.situacao)
    return qs


def achados(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.achados.models import Achado

    qs = Achado.objects.all()
    qs = _periodo(qs, filtros, "criado_em")
    qs = _origem(qs, filtros)
    qs = _por_prestacao(qs, filtros)
    if filtros.criticidade == "alta_ou_critica":
        from aplicacao.achados.escolhas import Criticidade

        qs = qs.filter(criticidade__in=[Criticidade.ALTA, Criticidade.CRITICA])
    elif filtros.criticidade:
        qs = qs.filter(criticidade=filtros.criticidade)
    if filtros.categoria:
        qs = qs.filter(categoria=filtros.categoria)
    if filtros.natureza:
        qs = qs.filter(natureza=filtros.natureza)
    if filtros.situacao:
        qs = qs.filter(status=filtros.situacao)
    if filtros.regra:
        qs = qs.filter(vinculos_regra__regra_id=filtros.regra).distinct()
    return qs


def evidencias(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.achados.models import Evidencia

    qs = Evidencia.objects.all()
    qs = _periodo(qs, filtros, "criada_em")
    qs = _origem(qs, filtros)
    qs = _por_prestacao(qs, filtros)
    if filtros.regra:
        qs = qs.filter(execucao_regra__regra_id=filtros.regra)
    return qs


def execucoes_regra(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.regras.models import ExecucaoRegra

    qs = ExecucaoRegra.objects.select_related("regra")
    qs = _periodo(qs, filtros, "criado_em") if _tem_criado_em(ExecucaoRegra) else qs
    qs = _por_prestacao(qs, filtros, "analise__prestacao_contas")
    if filtros.regra:
        qs = qs.filter(regra_id=filtros.regra)
    if filtros.categoria_regra:
        qs = qs.filter(regra__categoria=filtros.categoria_regra)
    if filtros.tipo_execucao:
        qs = qs.filter(regra__tipo_execucao=filtros.tipo_execucao)
    return qs


def _tem_criado_em(modelo) -> bool:
    return any(campo.name == "criado_em" for campo in modelo._meta.fields)


def pre_analises(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.pareceres.models import PreAnaliseTecnica

    qs = PreAnaliseTecnica.objects.all()
    qs = _periodo(qs, filtros, "criado_em")
    qs = _por_prestacao(qs, filtros)
    if filtros.origem == "demonstracao":
        qs = qs.filter(demonstracao=True)
    elif filtros.origem == "operacional":
        qs = qs.filter(demonstracao=False)
    if filtros.situacao:
        qs = qs.filter(status=filtros.situacao)
    return qs


def avaliacoes(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial

    qs = AvaliacaoInteligenciaArtificial.objects.all()
    qs = _periodo(qs, filtros, "criado_em")
    qs = _por_prestacao(qs, filtros)
    if filtros.origem == "demonstracao":
        qs = qs.filter(dados_demonstracao=True)
    elif filtros.origem == "operacional":
        qs = qs.filter(dados_demonstracao=False)
    return qs


def usos(filtros: FiltrosPainel) -> QuerySet:
    from aplicacao.inteligencia_artificial.models import UsoInteligenciaArtificial

    qs = UsoInteligenciaArtificial.objects.all()
    qs = _periodo(qs, filtros, "iniciada_em")
    if filtros.prestacao:
        qs = qs.filter(prestacao_contas_id=filtros.prestacao)
    if filtros.origem == "demonstracao":
        qs = qs.filter(prestacao_contas__demonstracao=True)
    elif filtros.origem == "operacional":
        qs = qs.filter(prestacao_contas__demonstracao=False)
    if filtros.agente:
        qs = qs.filter(agente=filtros.agente)
    if filtros.modelo:
        qs = qs.filter(modelo_id=filtros.modelo)
    if filtros.provedor:
        qs = qs.filter(provedor=filtros.provedor)
    return qs


def somar(qs: QuerySet, campo: str):
    return qs.aggregate(total=Sum(campo))["total"]


def contar_grupos(qs: QuerySet, campo: str) -> list[tuple[str, int]]:
    linhas = qs.values(campo).annotate(quantidade=Count("id")).order_by("-quantidade", campo)
    return [(linha[campo] or "", linha["quantidade"]) for linha in linhas]


def meses(qs: QuerySet, campo: str) -> list[tuple]:
    linhas = (
        qs.exclude(**{f"{campo}__isnull": True})
        .annotate(mes=TruncMonth(campo))
        .values("mes")
        .annotate(quantidade=Count("id"))
        .order_by("mes")
    )
    return [(linha["mes"], linha["quantidade"]) for linha in linhas if linha["mes"]]


def aviso_demonstracao(quantidade: int) -> list[str]:
    return []
