"""Opções dos filtros e montagem das abas analíticas."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q

from aplicacao.achados.escolhas import Criticidade, NaturezaAchado, PapelEvidencia, StatusAchado, StatusValidacaoEvidencia
from aplicacao.documentos.escolhas import MetodoExtracao, StatusProcessamento, TipoDocumento
from aplicacao.painel.consultas.filtros import FiltrosPainel, href
from aplicacao.painel.consultas.recortes import (
    achados,
    avaliacoes,
    aviso_demonstracao,
    contar_grupos,
    documentos,
    evidencias,
    execucoes_regra,
    meses,
    pre_analises,
    prestacoes,
    somar,
    usos,
)
from aplicacao.painel.consultas.tipos import (
    NAO_DISPONIVEL,
    SEM_HISTORICO,
    Grafico,
    Indicador,
    Linha,
    Ocorrencia,
    PainelAba,
    Serie,
    grafico,
    taxa,
    texto_contagem,
    texto_decimal,
)
from aplicacao.prestacoes_contas.escolhas import SituacaoPrestacao, TipoInstrumento
from django.urls import reverse

ORDEM_CRITICIDADE = {"critica": 0, "alta": 1, "media": 2, "baixa": 3, "informativa": 4}

CAMPOS_POR_ABA = {
    "visao": ["inicio", "fim", "prestacao", "situacao", "concedente", "beneficiario", "tipo_instrumento", "origem"],
    "processos": ["inicio", "fim", "prestacao", "situacao", "concedente", "beneficiario", "tipo_instrumento", "origem"],
    "documentos": ["inicio", "fim", "prestacao", "situacao", "tipo_documento", "origem"],
    "normas": ["inicio", "fim", "situacao"],
    "regras": ["inicio", "fim", "prestacao", "regra", "categoria_regra", "tipo_execucao", "origem"],
    "evidencias": ["inicio", "fim", "prestacao", "regra", "origem"],
    "achados": ["inicio", "fim", "prestacao", "situacao", "criticidade", "categoria", "natureza", "regra", "origem"],
    "pre_analise": ["inicio", "fim", "prestacao", "situacao", "origem"],
    "revisao": ["inicio", "fim", "prestacao", "responsavel", "origem"],
    "ia_tecnico": ["inicio", "fim", "prestacao", "origem"],
    "operacao": ["inicio", "fim", "prestacao", "agente", "modelo", "provedor", "origem"],
    "finops": ["inicio", "fim", "prestacao", "agente", "modelo", "provedor", "origem"],
}

ROTULOS_CAMPO = {
    "inicio": "Período inicial",
    "fim": "Período final",
    "prestacao": "Prestação",
    "situacao": "Situação",
    "concedente": "Concedente",
    "beneficiario": "Beneficiário",
    "tipo_instrumento": "Tipo de instrumento",
    "responsavel": "Responsável",
    "criticidade": "Criticidade",
    "categoria": "Categoria do achado",
    "natureza": "Natureza",
    "tipo_documento": "Tipo documental",
    "regra": "Regra",
    "categoria_regra": "Categoria da regra",
    "tipo_execucao": "Tipo de execução",
    "agente": "Agente",
    "modelo": "Modelo",
    "provedor": "Provedor",
    "origem": "Origem dos dados",
}


def _quando(valor) -> str:
    if not valor:
        return ""
    return valor.strftime("%d/%m/%Y %H:%M")


def _kpi(nome: str, exibicao: str, url: str = "", observacao: str = "", complemento: str = "") -> Indicador:
    return Indicador(nome=nome, exibicao=exibicao, url=url, observacao=observacao, complemento=complemento)


def _com_peso(etapas: list[Indicador]) -> list[Indicador]:
    numeros = [int(etapa.exibicao) if etapa.exibicao.isdigit() else 0 for etapa in etapas]
    maior = max(numeros, default=0)
    for etapa, numero in zip(etapas, numeros):
        etapa.peso = int(round(100 * numero / maior)) if maior else 0
    return etapas


def _reais(valor) -> str:
    if valor is None:
        return NAO_DISPONIVEL
    texto = format(Decimal(valor).quantize(Decimal("0.01")), "f")
    inteiro, fracao = texto.split(".")
    return f"R$ {inteiro},{fracao}"


def _rotulo(mapa, chave: str) -> str:
    if hasattr(mapa, "choices"):
        return dict(mapa.choices).get(chave, chave or "Não informado")
    return dict(mapa).get(chave, chave or "Não informado")


def _series_grupo(pares, mapa, url_nome, filtros, parametro, vazio_rotulo="Não informado") -> list[Serie]:
    series = []
    for chave, quantidade in pares:
        rotulo = _rotulo(mapa, chave) if chave else vazio_rotulo
        extra = {parametro: chave} if chave else {}
        series.append(Serie(rotulo, quantidade, texto_contagem(quantidade), href(url_nome, filtros, **extra) if extra else href(url_nome, filtros)))
    return series


def descrever_campos(aba: str, filtros: FiltrosPainel, opcoes: dict) -> list[dict]:
    origem_opcoes = {
        "prestacao": opcoes["prestacoes"],
        "situacao": opcoes["situacoes"],
        "concedente": opcoes["concedentes"],
        "beneficiario": opcoes["beneficiarios"],
        "tipo_instrumento": opcoes["instrumentos"],
        "responsavel": opcoes["responsaveis"],
        "criticidade": opcoes["criticidades"],
        "natureza": opcoes["naturezas"],
        "tipo_documento": opcoes["tipos_documento"],
        "regra": opcoes["regras"],
        "categoria_regra": [(item, item) for item in opcoes["categorias_regra"]],
        "categoria": [(item, item) for item in opcoes["categorias"]],
        "tipo_execucao": opcoes["tipos_execucao"],
        "agente": [(item, item) for item in opcoes["agentes"]],
        "modelo": opcoes["modelos"],
        "provedor": opcoes["provedores"],
        "origem": opcoes["origens"],
    }
    campos = []
    for nome in CAMPOS_POR_ABA[aba]:
        valor = getattr(filtros, nome)
        if hasattr(valor, "isoformat"):
            exibicao = valor.isoformat()
        else:
            exibicao = "" if valor is None else str(valor)
        campos.append(
            {
                "nome": nome,
                "rotulo": ROTULOS_CAMPO[nome],
                "valor": exibicao,
                "data": nome in {"inicio", "fim"},
                "opcoes": origem_opcoes.get(nome, []),
            }
        )
    return campos


def opcoes_de_filtro(aba: str, origem: str = "") -> dict:
    from aplicacao.entidades.models import Entidade
    from aplicacao.regras.escolhas import TipoExecucaoTecnica
    from aplicacao.inteligencia_artificial.escolhas import ProvedorIA
    from aplicacao.inteligencia_artificial.models import ModeloInteligenciaArtificial, UsoInteligenciaArtificial
    from aplicacao.pareceres.escolhas import StatusPreAnalise
    from aplicacao.prestacoes_contas.models import PrestacaoContas
    from aplicacao.regras.models import RegraAnalise
    from aplicacao.usuarios.models import Usuario

    situacoes = {
        "documentos": StatusProcessamento.choices,
        "normas": [("vigente", "Vigente"), ("nao_vigente", "Não vigente")],
        "achados": StatusAchado.choices,
        "pre_analise": StatusPreAnalise.choices,
    }.get(aba, SituacaoPrestacao.choices)
    prestacoes = PrestacaoContas.objects.order_by("numero_processo")
    if origem == "demonstracao":
        prestacoes = prestacoes.filter(demonstracao=True)
    elif origem == "operacional":
        prestacoes = prestacoes.filter(demonstracao=False)
    return {
        "situacoes": situacoes,
        "prestacoes": list(prestacoes.values_list("id", "numero_processo")[:300]),
        "concedentes": list(Entidade.objects.filter(prestacoes_como_concedente__isnull=False).order_by("nome").distinct().values_list("id", "nome")[:200]),
        "beneficiarios": list(Entidade.objects.filter(prestacoes_como_beneficiario__isnull=False).order_by("nome").distinct().values_list("id", "nome")[:200]),
        "instrumentos": TipoInstrumento.choices,
        "criticidades": Criticidade.choices,
        "naturezas": NaturezaAchado.choices,
        "categorias": list(achados(FiltrosPainel()).exclude(categoria="").order_by("categoria").values_list("categoria", flat=True).distinct()[:80]),
        "tipos_documento": TipoDocumento.choices,
        "regras": list(RegraAnalise.objects.order_by("codigo").values_list("id", "codigo")[:120]),
        "categorias_regra": list(RegraAnalise.objects.exclude(categoria="").order_by("categoria").values_list("categoria", flat=True).distinct()),
        "tipos_execucao": TipoExecucaoTecnica.choices,
        "agentes": list(UsoInteligenciaArtificial.objects.exclude(agente="").order_by("agente").values_list("agente", flat=True).distinct()[:80]),
        "modelos": list(ModeloInteligenciaArtificial.objects.order_by("nome_exibicao").values_list("id", "nome_exibicao")[:80]),
        "provedores": ProvedorIA.choices,
        "responsaveis": list(Usuario.objects.order_by("username").values_list("id", "username")[:200]),
        "origens": [("demonstracao", "Somente demonstração"), ("operacional", "Somente operacionais")],
    }


def _avisos(qs) -> list[str]:
    if not hasattr(qs.model, "demonstracao"):
        return []
    return aviso_demonstracao(qs.filter(demonstracao=True).count())


def _contar_resultado(qs, *textos: str) -> int:
    condicao = Q()
    for texto in textos:
        condicao |= Q(resultado_funcional__iexact=texto)
    return qs.filter(condicao).count()


def _historico(blocos: list[tuple[str, list]]) -> tuple[Grafico | None, str]:
    series: list[Serie] = []
    for nome, pontos in blocos:
        if len(pontos) < 2:
            continue
        for mes, quantidade in pontos:
            series.append(Serie(f"{mes:%Y-%m} · {nome}", quantidade, texto_contagem(quantidade)))
    if not series:
        return None, SEM_HISTORICO
    return grafico(
        "Evolução das análises",
        "Cada série entra somente quando há pelo menos dois meses distintos. Meses ausentes não são preenchidos com zero.",
        series,
        SEM_HISTORICO,
    ), ""


def montar_visao(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.achados.models import Achado, Evidencia
    from aplicacao.documentos.models import Documento
    from aplicacao.pareceres.models import PreAnaliseTecnica
    from aplicacao.regras.models import ExecucaoRegra

    carteira = prestacoes(filtros)
    ids = list(carteira.values_list("pk", flat=True))
    docs = Documento.objects.filter(excluido_em__isnull=True, prestacao_contas_id__in=ids)
    execs = ExecucaoRegra.objects.filter(analise__prestacao_contas_id__in=ids)
    evids = Evidencia.objects.filter(prestacao_contas_id__in=ids)
    achs = Achado.objects.filter(prestacao_contas_id__in=ids)
    pres = PreAnaliseTecnica.objects.filter(prestacao_contas_id__in=ids)
    criticos = achs.filter(criticidade__in=[Criticidade.ALTA, Criticidade.CRITICA])
    materialidade = somar(achs, "materialidade_financeira")
    estagio = filtros.alterar(situacao="")
    com_achados = carteira.filter(achados__isnull=False).distinct().count()
    total_carteira = carteira.count()
    situacoes = dict(contar_grupos(carteira, "situacao"))
    series_etapa = [
        Serie(rotulo, situacoes.get(chave, 0), texto_contagem(situacoes.get(chave, 0)), href("painel:processos", filtros, situacao=chave))
        for chave, rotulo in SituacaoPrestacao.choices
    ]
    series_natureza = sorted(
        _series_grupo(contar_grupos(achs, "natureza"), NaturezaAchado, "painel:achados", estagio, "natureza"),
        key=lambda item: item.quantidade or 0,
        reverse=True,
    )
    historico, mensagem = _historico(
        [
            ("Prestações", meses(carteira, "criado_em")),
            ("Documentos", meses(docs, "criado_em")),
            ("Regras executadas", meses(execs, "criado_em")),
            ("Evidências", meses(evids, "criada_em")),
            ("Achados", meses(achs, "criado_em")),
            ("Pré-análises", meses(pres, "criado_em")),
        ]
    )
    return PainelAba(
        kpis=[
            _kpi("Prestações cadastradas", texto_contagem(carteira.count()), href("painel:processos", estagio)),
            _kpi("Em análise", texto_contagem(carteira.filter(situacao=SituacaoPrestacao.EM_ANALISE).count()), href("painel:processos", filtros.alterar(situacao=SituacaoPrestacao.EM_ANALISE))),
            _kpi("Concluídas", texto_contagem(carteira.filter(situacao=SituacaoPrestacao.CONCLUIDA).count()), href("painel:processos", filtros.alterar(situacao=SituacaoPrestacao.CONCLUIDA))),
            _kpi("Achados críticos", texto_contagem(criticos.count()), href("painel:achados", estagio.alterar(criticidade="alta_ou_critica")), "Alta ou crítica, conforme o cadastro do achado. O atalho reúne as duas criticidades já existentes."),
            _kpi("Com achados", texto_contagem(com_achados), href("painel:achados", estagio), complemento=f"de {total_carteira}"),
            _kpi("Materialidade dos achados", _reais(materialidade), href("painel:achados", estagio), "Soma somente materialidades informadas. Ausência não entra como zero."),
        ],
        graficos=[
            grafico("Processos por etapa", "Situação cadastrada. Não é um SLA.", series_etapa, "Sem prestações para os filtros selecionados.", incluir_zeros=True),
            grafico("Distribuição dos achados por criticidade", "Criticidade registrada no achado.", _series_grupo(contar_grupos(achs, "criticidade"), Criticidade, "painel:achados", estagio, "criticidade"), "Sem achados para os filtros selecionados." if not achs.exists() else "Criticidade ainda não registrada nos achados.", formato="donut", centro="Achados"),
            grafico("Achados por natureza", "Natureza registrada no achado.", series_natureza, "Sem achados para os filtros selecionados."),
        ],
        pipeline=_com_peso([
            _kpi("Documentos", texto_contagem(docs.count()), href("painel:documentos", estagio)),
            _kpi("Regras executadas", texto_contagem(execs.count()), href("painel:regras", estagio)),
            _kpi("Evidências", texto_contagem(evids.count()), href("painel:evidencias", estagio)),
            _kpi("Achados", texto_contagem(achs.count()), href("painel:achados", estagio)),
            _kpi("Pré-análises", texto_contagem(pres.count()), href("painel:pre_analise", estagio)),
            _kpi("Revisões humanas", texto_contagem(_revisoes_no_recorte(ids)), href("painel:revisao", estagio)),
        ]),
        atencao=_atencao(ids),
        historico=historico,
        mensagem_historico=mensagem,
        avisos=_avisos(carteira),
    )


def _revisoes_no_recorte(ids: list[int]) -> int:
    from aplicacao.achados.models import RevisaoAchado
    from aplicacao.avaliacao.models import RevisaoCorrespondencia
    from aplicacao.pareceres.models import RevisaoPreAnalise

    return (
        RevisaoAchado.objects.filter(achado__prestacao_contas_id__in=ids).count()
        + RevisaoPreAnalise.objects.filter(pre_analise__prestacao_contas_id__in=ids).count()
        + RevisaoCorrespondencia.objects.filter(correspondencia__avaliacao__prestacao_contas_id__in=ids).count()
    )


def _atencao(ids: list[int]) -> list[Ocorrencia]:
    from aplicacao.achados.models import Achado
    from aplicacao.avaliacao.escolhas import ClassificacaoCorrespondencia, CriticidadeReferencia, StatusAvaliacao
    from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial, CorrespondenciaAchado
    from aplicacao.documentos.escolhas import StatusProcessamento as StatusDoc
    from aplicacao.documentos.models import Documento
    from aplicacao.inteligencia_artificial.escolhas import StatusUso
    from aplicacao.inteligencia_artificial.models import UsoInteligenciaArtificial
    from aplicacao.pareceres.escolhas import StatusPreAnalise
    from aplicacao.pareceres.models import PreAnaliseTecnica
    from aplicacao.regras.models import ExecucaoRegra

    itens: list[tuple[int, str, Ocorrencia]] = []

    def acrescentar(ordem: int, momento, ocorrencia: Ocorrencia):
        itens.append((ordem, momento.isoformat() if momento else "", ocorrencia))

    for achado in Achado.objects.filter(prestacao_contas_id__in=ids, criticidade__in=[Criticidade.ALTA, Criticidade.CRITICA]).select_related("prestacao_contas")[:8]:
        acrescentar(ORDEM_CRITICIDADE.get(achado.criticidade, 9), achado.criado_em, Ocorrencia("Achado crítico", achado.titulo, _quando(achado.criado_em), achado.prestacao_contas.numero_processo, achado.get_criticidade_display(), reverse("achados:detalhe", kwargs={"pk": achado.pk})))
    for achado in Achado.objects.filter(prestacao_contas_id__in=ids, status=StatusAchado.EM_REVISAO).select_related("prestacao_contas")[:5]:
        acrescentar(2, achado.criado_em, Ocorrencia("Achado em revisão", achado.titulo, _quando(achado.criado_em), achado.prestacao_contas.numero_processo, achado.get_criticidade_display(), reverse("achados:detalhe", kwargs={"pk": achado.pk})))
    for documento in Documento.objects.filter(prestacao_contas_id__in=ids, status_processamento__in=[StatusDoc.AGUARDANDO_VALIDACAO, StatusDoc.ERRO]).select_related("prestacao_contas")[:5]:
        acrescentar(3, documento.criado_em, Ocorrencia("Documento", documento.nome_original, _quando(documento.criado_em), documento.prestacao_contas.numero_processo, documento.get_status_processamento_display(), reverse("documentos:detalhe", kwargs={"pk": documento.pk})))
    for execucao in ExecucaoRegra.objects.filter(analise__prestacao_contas_id__in=ids).filter(Q(resultado_funcional__iexact="NÃO VERIFICÁVEL") | Q(resultado_funcional__iexact="NÃO LOCALIZADO")).select_related("regra", "analise__prestacao_contas")[:5]:
        acrescentar(4, execucao.criado_em, Ocorrencia(execucao.resultado_funcional, execucao.regra.codigo, _quando(execucao.criado_em), execucao.analise.prestacao_contas.numero_processo, "", reverse("regras:detalhe", kwargs={"codigo": execucao.regra.codigo})))
    for pre in PreAnaliseTecnica.objects.filter(prestacao_contas_id__in=ids, status=StatusPreAnalise.AGUARDANDO_REVISAO).select_related("prestacao_contas")[:5]:
        acrescentar(3, pre.criado_em, Ocorrencia("Pré-análise aguardando revisão", pre.codigo, _quando(pre.criado_em), pre.prestacao_contas.numero_processo, "", reverse("pareceres:detalhe", kwargs={"pk": pre.pk})))
    for item in CorrespondenciaAchado.objects.filter(avaliacao__prestacao_contas_id__in=ids, classificacao=ClassificacaoCorrespondencia.PENDENTE_REVISAO).select_related("avaliacao__prestacao_contas")[:5]:
        acrescentar(3, item.avaliacao.criado_em, Ocorrencia("Correspondência pendente", item.avaliacao.codigo, _quando(item.avaliacao.criado_em), item.avaliacao.prestacao_contas.numero_processo, "", reverse("avaliacao:detalhe", kwargs={"pk": item.avaliacao_id})))
    for item in CorrespondenciaAchado.objects.filter(
        avaliacao__prestacao_contas_id__in=ids,
        classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO,
        ground_truth_achado__criticidade__in=[CriticidadeReferencia.ALTA, CriticidadeReferencia.CRITICA],
    ).select_related("avaliacao", "ground_truth_achado")[:5]:
        acrescentar(0, item.avaliacao.criado_em, Ocorrencia("Falso negativo crítico", item.ground_truth_achado.titulo, _quando(item.avaliacao.criado_em), item.avaliacao.prestacao_contas.numero_processo, item.ground_truth_achado.get_criticidade_display(), reverse("avaliacao:falso_negativo", kwargs={"pk": item.avaliacao_id, "correspondencia_pk": item.pk})))
    for uso in UsoInteligenciaArtificial.objects.filter(prestacao_contas_id__in=ids, status=StatusUso.ERRO_CONTROLADO).select_related("prestacao_contas")[:5]:
        acrescentar(2, uso.iniciada_em, Ocorrencia("Falha de IA", uso.erro_normalizado or uso.get_status_display(), _quando(uso.iniciada_em), uso.prestacao_contas.numero_processo if uso.prestacao_contas_id else "", "", href("painel:operacao")))
    for avaliacao in AvaliacaoInteligenciaArtificial.objects.filter(prestacao_contas_id__in=ids, status__in=[StatusAvaliacao.AGUARDANDO_REVISAO, StatusAvaliacao.AGUARDANDO_GROUND_TRUTH]).select_related("prestacao_contas")[:5]:
        acrescentar(3, avaliacao.criado_em, Ocorrencia("Avaliação aguardando ação", avaliacao.codigo, _quando(avaliacao.criado_em), avaliacao.prestacao_contas.numero_processo, "", reverse("avaliacao:detalhe", kwargs={"pk": avaliacao.pk})))
    itens.sort(key=lambda item: item[1], reverse=True)
    itens.sort(key=lambda item: item[0])
    return [item[2] for item in itens[:12]]
