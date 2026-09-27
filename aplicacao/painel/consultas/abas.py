"""Abas analíticas do Painel, fora da Visão 360°."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.urls import reverse

from aplicacao.achados.escolhas import Criticidade, PapelEvidencia, StatusAchado, StatusValidacaoEvidencia
from aplicacao.avaliacao.escolhas import ClassificacaoCorrespondencia, CriticidadeReferencia
from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao, StatusProcessamento, TipoDocumento
from aplicacao.normas.escolhas import SituacaoNorma, StatusProcessamentoNorma
from aplicacao.painel.consultas.filtros import FiltrosPainel, href
from aplicacao.painel.consultas.recortes import (
    achados,
    avaliacoes,
    contar_grupos,
    documentos,
    evidencias,
    execucoes_regra,
    pre_analises,
    prestacoes,
    somar,
    usos,
)
from aplicacao.painel.consultas.tipos import NAO_DISPONIVEL, Indicador, Linha, PainelAba, Serie, grafico, taxa, texto_contagem, texto_decimal
from aplicacao.pareceres.escolhas import EncaminhamentoPreAnalise, OrigemConteudo, StatusPreAnalise
from aplicacao.prestacoes_contas.escolhas import FasePrestacao, SituacaoPrestacao, TipoInstrumento
from aplicacao.regras.escolhas import FONTE_EXCLUIDA_TESTE_CEGO, CapacidadeExecucao, TipoExecucaoTecnica


def _kpi(nome, exibicao, url="", observacao="") -> Indicador:
    return Indicador(nome, exibicao, url, observacao)


def _rotulo(choices, chave: str) -> str:
    return dict(choices).get(chave, chave or "Não informado")


def _por_choices(titulo, descricao, pares, choices, vazio) -> object:
    series = [Serie(_rotulo(choices, chave), quantidade, texto_contagem(quantidade)) for chave, quantidade in pares if quantidade]
    return grafico(titulo, descricao, series, vazio)


def _aviso(qs, campo="demonstracao") -> list[str]:
    return []


def montar_processos(filtros: FiltrosPainel) -> PainelAba:
    qs = prestacoes(filtros).annotate(q_achados=Count("achados", distinct=True))
    por_tipo = (
        qs.filter(instrumentos__principal=True)
        .values("instrumentos__tipo")
        .annotate(quantidade=Count("id", distinct=True))
        .order_by("-quantidade")
    )
    series_tipo = [
        Serie(_rotulo(TipoInstrumento.choices, linha["instrumentos__tipo"]), linha["quantidade"], texto_contagem(linha["quantidade"]))
        for linha in por_tipo
        if linha["quantidade"]
    ]
    linhas = [
        Linha(
            [
                item.numero_processo,
                item.get_situacao_display(),
                item.get_fase_display(),
                texto_contagem(item.q_achados),
                "Sim" if item.demonstracao else "Não",
            ],
            reverse("prestacoes_contas:detalhe", kwargs={"pk": item.pk}),
        )
        for item in qs.select_related("concedente", "beneficiario")[:80]
    ]
    return PainelAba(
        kpis=[
            _kpi("Prestações", texto_contagem(qs.count()), href("painel:processos", filtros)),
            _kpi("Em análise", texto_contagem(qs.filter(situacao=SituacaoPrestacao.EM_ANALISE).count())),
            _kpi("Concluídas", texto_contagem(qs.filter(situacao=SituacaoPrestacao.CONCLUIDA).count())),
            _kpi("Com achados", texto_contagem(qs.filter(q_achados__gt=0).count())),
            _kpi("Sem achados", texto_contagem(qs.filter(q_achados=0).count())),
        ],
        graficos=[
            _por_choices("Prestações por situação", "Situação cadastrada. Não é SLA.", contar_grupos(prestacoes(filtros), "situacao"), SituacaoPrestacao.choices, "Sem prestações para os filtros selecionados."),
            _por_choices("Prestações por fase", "Fase cadastrada do processo.", contar_grupos(prestacoes(filtros), "fase"), FasePrestacao.choices, "Sem prestações para os filtros selecionados."),
            grafico("Por tipo de instrumento principal", "Somente o instrumento marcado como principal.", series_tipo, "Sem instrumento principal no recorte."),
        ],
        colunas=["Processo", "Situação", "Fase", "Achados", "Demonstração"],
        linhas=linhas,
        vazio_tabela="Sem prestações para os filtros selecionados.",
        avisos=_aviso(prestacoes(filtros)),
    )


def montar_documentos(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.documentos.models import PaginaDocumento

    qs = documentos(filtros)
    paginas = PaginaDocumento.objects.filter(documento__in=qs)
    usados = qs.filter(evidencias__isnull=False).distinct().count()
    paginas_total = somar(qs, "quantidade_paginas")
    linhas = [
        Linha(
            [item.nome_original, item.get_tipo_documento_display(), item.get_status_processamento_display(), item.prestacao_contas.numero_processo],
            reverse("documentos:detalhe", kwargs={"pk": item.pk}),
        )
        for item in qs.select_related("prestacao_contas")[:80]
    ]
    return PainelAba(
        kpis=[
            _kpi("Recebidos", texto_contagem(qs.count())),
            _kpi("Processados", texto_contagem(qs.filter(status_processamento=StatusProcessamento.PROCESSADO).count())),
            _kpi("Aguardando validação", texto_contagem(qs.filter(status_processamento=StatusProcessamento.AGUARDANDO_VALIDACAO).count())),
            _kpi("Com erro", texto_contagem(qs.filter(status_processamento=StatusProcessamento.ERRO).count())),
            _kpi("Páginas", texto_decimal(paginas_total, Decimal("1")) if False else (texto_contagem(int(paginas_total)) if paginas_total is not None else NAO_DISPONIVEL), observacao="Soma de quantidade_paginas. Permanece não disponível quando nenhuma página foi informada."),
            _kpi("Usados como evidência", texto_contagem(usados)),
            _kpi("Ainda não usados como evidência", texto_contagem(qs.filter(evidencias__isnull=True).count())),
            _kpi("Excluídos do teste cego", texto_contagem(qs.filter(subtipo_documento=FONTE_EXCLUIDA_TESTE_CEGO).count()), observacao="Subtipo reservado à fonte excluída do teste cego. Não entra como evidência válida da análise cega."),
        ],
        graficos=[
            _por_choices("Documentos por tipo", "Tipo documental cadastrado.", contar_grupos(qs, "tipo_documento"), TipoDocumento.choices, "Sem documentos para os filtros selecionados."),
            _por_choices("Método de extração", "Método registrado na página. Documento sem página não entra neste gráfico.", contar_grupos(paginas, "metodo_extracao"), MetodoExtracao.choices, "Sem páginas extraídas no recorte."),
            _por_choices("Status de processamento", "Status do documento.", contar_grupos(qs, "status_processamento"), StatusProcessamento.choices, "Sem documentos para os filtros selecionados."),
            _por_choices("Qualidade da extração", "Qualidade registrada na página.", contar_grupos(paginas, "qualidade_extracao"), QualidadeExtracao.choices, "Sem páginas extraídas no recorte."),
        ],
        colunas=["Documento", "Tipo", "Status", "Prestação"],
        linhas=linhas,
        vazio_tabela="Sem documentos para os filtros selecionados.",
        avisos=_aviso(qs),
    )


def _normas(filtros: FiltrosPainel):
    from aplicacao.normas.models import Norma

    qs = Norma.objects.all()
    if filtros.inicio:
        qs = qs.filter(criado_em__date__gte=filtros.inicio)
    if filtros.fim:
        qs = qs.filter(criado_em__date__lte=filtros.fim)
    if filtros.situacao == "vigente":
        qs = qs.filter(situacao=SituacaoNorma.VIGENTE)
    elif filtros.situacao == "nao_vigente":
        qs = qs.exclude(situacao=SituacaoNorma.VIGENTE)
    elif filtros.situacao:
        qs = qs.filter(situacao=filtros.situacao)
    return qs


def montar_normas(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.achados.models import FundamentacaoAchado
    from aplicacao.normas.models import AplicabilidadeNorma, ConsultaNormativa, TrechoNormativo

    qs = _normas(filtros)
    fundamentacoes = FundamentacaoAchado.objects.filter(norma__in=qs)
    vigentes_usadas = fundamentacoes.filter(norma__situacao=SituacaoNorma.VIGENTE).values("norma_id").distinct().count()
    nao_vigentes_usadas = fundamentacoes.exclude(norma__situacao=SituacaoNorma.VIGENTE).values("norma_id").distinct().count()
    aplicabilidades = AplicabilidadeNorma.objects.filter(norma__in=qs)
    return PainelAba(
        kpis=[
            _kpi("Normas cadastradas", texto_contagem(qs.count()), reverse("normas:lista")),
            _kpi("Vigentes", texto_contagem(qs.filter(situacao=SituacaoNorma.VIGENTE).count())),
            _kpi("Não vigentes", texto_contagem(qs.exclude(situacao=SituacaoNorma.VIGENTE).count()), observacao="Revogada, substituída ou alterada não fundamenta análise."),
            _kpi("Processadas", texto_contagem(qs.filter(status_processamento=StatusProcessamentoNorma.DISPONIVEL).count())),
            _kpi("Com erro", texto_contagem(qs.filter(status_processamento=StatusProcessamentoNorma.ERRO).count())),
            _kpi("Trechos indexados", texto_contagem(TrechoNormativo.objects.filter(norma__in=qs).count())),
            _kpi("Aplicabilidades", texto_contagem(aplicabilidades.count())),
            _kpi("Consultas normativas", texto_contagem(ConsultaNormativa.objects.count()), observacao="A consulta normativa não é filtrada por prestação: o registro não pertence a um processo."),
            _kpi("Usadas em fundamentação vigente", texto_contagem(vigentes_usadas)),
            _kpi("Citações de norma não vigente", texto_contagem(nao_vigentes_usadas), observacao="Contagem de rastreio. Não são fundamentação válida."),
        ],
        graficos=[
            _por_choices("Normas por situação", "Situação da norma. Fora de vigência não é fundamento válido.", contar_grupos(qs, "situacao"), SituacaoNorma.choices, "Sem normas para os filtros selecionados."),
            grafico(
                "Normas por aplicabilidade",
                "Tipo de instrumento informado na aplicabilidade. Vazio significa que aquele eixo não restringe.",
                [Serie(chave or "Sem restrição de instrumento", quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(aplicabilidades, "tipo_instrumento") if quantidade],
                "Sem aplicabilidades no recorte.",
            ),
        ],
        colunas=["Norma", "Situação", "Processamento"],
        linhas=[
            Linha([item.titulo, item.get_situacao_display(), item.get_status_processamento_display()], reverse("normas:detalhe", kwargs={"pk": item.pk}))
            for item in qs[:80]
        ],
        vazio_tabela="Sem normas para os filtros selecionados.",
    )


def montar_regras(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.regras.models import RegraAnalise

    catalogo = RegraAnalise.objects.all()
    if filtros.categoria_regra:
        catalogo = catalogo.filter(categoria=filtros.categoria_regra)
    if filtros.tipo_execucao:
        catalogo = catalogo.filter(tipo_execucao=filtros.tipo_execucao)
    if filtros.regra:
        catalogo = catalogo.filter(pk=filtros.regra)
    execucoes = execucoes_regra(filtros)
    executadas = set(execucoes.values_list("regra_id", flat=True))
    return PainelAba(
        kpis=[
            _kpi("Regras cadastradas", texto_contagem(catalogo.count()), reverse("regras:lista"), "Contagem do catálogo no recorte de regra, categoria e tipo. O texto original da regra não é alterado."),
            _kpi("Executadas no recorte", texto_contagem(len(executadas))),
            _kpi("Não executadas no recorte", texto_contagem(catalogo.exclude(pk__in=executadas or [0]).count())),
            _kpi("Automáticas", texto_contagem(catalogo.filter(capacidade=CapacidadeExecucao.AUTOMATICA).count())),
            _kpi("Parciais", texto_contagem(catalogo.filter(capacidade=CapacidadeExecucao.PARCIAL).count())),
            _kpi("Requer IA", texto_contagem(catalogo.filter(capacidade=CapacidadeExecucao.REQUER_IA).count())),
            _kpi("Requer analista", texto_contagem(catalogo.filter(capacidade=CapacidadeExecucao.REQUER_ANALISTA).count())),
            _kpi("Fora do escopo", texto_contagem(catalogo.filter(tipo_execucao=TipoExecucaoTecnica.FORA_ESCOPO_V1).count())),
            _kpi("Conformes", texto_contagem(execucoes.filter(resultado_funcional__iexact="CONFORME").count())),
            _kpi("Divergentes", texto_contagem(execucoes.filter(resultado_funcional__iexact="DIVERGÊNCIA").count())),
            _kpi("Não verificáveis", texto_contagem(execucoes.filter(resultado_funcional__iexact="NÃO VERIFICÁVEL").count()), observacao="Igualdade textual do resultado funcional. Não se confunde com não aplicável."),
            _kpi("Não localizadas", texto_contagem(execucoes.filter(resultado_funcional__iexact="NÃO LOCALIZADO").count())),
            _kpi("Com erro técnico", texto_contagem(execucoes.filter(status_tecnico="erro").count())),
        ],
        graficos=[
            grafico("Regras por categoria", "Categoria do catálogo.", [Serie(chave or "Sem categoria", quantidade, texto_contagem(quantidade), reverse("regras:lista")) for chave, quantidade in contar_grupos(catalogo, "categoria") if quantidade], "Sem regras no recorte."),
            _por_choices("Regras por tipo de execução", "Tipo técnico do catálogo.", contar_grupos(catalogo, "tipo_execucao"), TipoExecucaoTecnica.choices, "Sem regras no recorte."),
            grafico(
                "Resultados das verificações",
                "Resultado funcional das execuções do recorte, sem normalizar não aplicável, não verificável e não localizado.",
                [Serie(rotulo, quantidade, texto_contagem(quantidade)) for rotulo, quantidade in _resultados(execucoes) if quantidade],
                "Sem execuções para os filtros selecionados.",
            ),
            _por_choices("Automação das regras", "Capacidade cadastrada no catálogo.", contar_grupos(catalogo, "capacidade"), CapacidadeExecucao.choices, "Sem regras no recorte."),
        ],
        colunas=["Regra", "Categoria", "Tipo", "Execuções no recorte"],
        linhas=[
            Linha(
                [regra.codigo, regra.categoria, regra.get_tipo_execucao_display(), texto_contagem(execucoes.filter(regra=regra).count())],
                reverse("regras:detalhe", kwargs={"codigo": regra.codigo}),
            )
            for regra in catalogo.order_by("codigo")[:89]
        ],
        vazio_tabela="Sem regras no recorte.",
    )


def _resultados(execucoes) -> list[tuple[str, int]]:
    rotulos = (
        ("CONFORME", "Conforme"),
        ("DIVERGÊNCIA", "Divergência"),
        ("NÃO VERIFICÁVEL", "Não verificável"),
        ("NÃO LOCALIZADO", "Não localizado"),
        ("NÃO APLICÁVEL", "Não aplicável"),
    )
    conhecidos = Q()
    saida = []
    for texto, rotulo in rotulos:
        quantidade = execucoes.filter(resultado_funcional__iexact=texto).count()
        saida.append((rotulo, quantidade))
        conhecidos |= Q(resultado_funcional__iexact=texto)
    outros = execucoes.exclude(conhecidos).exclude(resultado_funcional="").count()
    if outros:
        saida.append(("Outros resultados", outros))
    return saida


def montar_evidencias(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.achados.models import AchadoEvidencia

    qs = evidencias(filtros)
    vinculos = AchadoEvidencia.objects.filter(evidencia__in=qs)
    orfas = qs.filter(documento__isnull=True, execucao_regra__isnull=True, vinculos__isnull=True)
    return PainelAba(
        kpis=[
            _kpi("Evidências", texto_contagem(qs.count())),
            _kpi("Suportam", texto_contagem(vinculos.filter(papel=PapelEvidencia.SUPORTA).count())),
            _kpi("Contradizem", texto_contagem(vinculos.filter(papel=PapelEvidencia.CONTRADIZ).count())),
            _kpi("Contextualizam", texto_contagem(vinculos.filter(papel=PapelEvidencia.CONTEXTUALIZA).count())),
            _kpi("Validadas", texto_contagem(qs.filter(status_validacao=StatusValidacaoEvidencia.VALIDADA).count())),
            _kpi("Aguardando revisão", texto_contagem(qs.filter(status_validacao=StatusValidacaoEvidencia.PENDENTE).count())),
            _kpi("Órfãs", texto_contagem(orfas.count()), observacao="Sem documento, sem execução de regra e sem achado. Isso não torna a evidência inválida."),
            _kpi("Vinculadas a regra", texto_contagem(qs.filter(execucao_regra__isnull=False).count())),
            _kpi("Vinculadas a achado", texto_contagem(qs.filter(vinculos__isnull=False).distinct().count())),
        ],
        graficos=[
            _por_choices("Evidências por papel no achado", "Papel do vínculo. Evidência sem achado não aparece aqui.", contar_grupos(vinculos, "papel"), PapelEvidencia.choices, "Sem vínculos de evidência no recorte."),
            _por_choices("Evidências por tipo", "Tipo cadastrado da evidência.", contar_grupos(qs, "tipo"), [], "Sem evidências para os filtros selecionados.")
            if False else grafico("Evidências por tipo", "Tipo cadastrado da evidência.", [Serie(chave or "Não informado", quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(qs, "tipo") if quantidade], "Sem evidências para os filtros selecionados."),
        ],
        colunas=["Código", "Tipo", "Validação", "Prestação", "Órfã"],
        linhas=[
            Linha(
                [
                    item.codigo,
                    item.get_tipo_display(),
                    item.get_status_validacao_display(),
                    item.prestacao_contas.numero_processo,
                    "Sim" if item.documento_id is None and item.execucao_regra_id is None and not item.vinculos.exists() else "Não",
                ],
                reverse("documentos:detalhe", kwargs={"pk": item.documento_id}) if item.documento_id else reverse("prestacoes_contas:detalhe", kwargs={"pk": item.prestacao_contas_id}),
            )
            for item in qs.select_related("prestacao_contas")[:80]
        ],
        vazio_tabela="Sem evidências para os filtros selecionados.",
        avisos=_aviso(qs),
    )


def montar_achados(filtros: FiltrosPainel) -> PainelAba:
    qs = achados(filtros)
    com_valor = qs.filter(materialidade_financeira__isnull=False)
    return PainelAba(
        kpis=[
            _kpi("Achados", texto_contagem(qs.count())),
            _kpi("Aguardando revisão", texto_contagem(qs.filter(status=StatusAchado.EM_REVISAO).count())),
            _kpi("Confirmados", texto_contagem(qs.filter(status=StatusAchado.CONFIRMADO).count())),
            _kpi("Críticos", texto_contagem(qs.filter(criticidade__in=[Criticidade.ALTA, Criticidade.CRITICA]).count()), observacao="Criticidade alta ou crítica já existente no achado."),
            _kpi("Com materialidade", texto_contagem(com_valor.count())),
            _kpi("Sem materialidade", texto_contagem(qs.filter(materialidade_financeira__isnull=True).count())),
            _kpi("Materialidade total", texto_decimal(somar(qs, "materialidade_financeira")), observacao="Soma apenas valores existentes."),
            _kpi("Rastreáveis", texto_contagem(qs.filter(elementos_rastreaveis=True).count())),
            _kpi("Fundamentação insuficiente", texto_contagem(qs.filter(fundamentacao_suficiente=False).count()), observacao="Usa o indicador já gravado no achado. Não cria uma nova classificação."),
        ],
        graficos=[
            _por_choices("Achados por status", "Status do achado.", contar_grupos(qs, "status"), StatusAchado.choices, "Sem achados para os filtros selecionados."),
            _por_choices("Achados por criticidade", "Criticidade cadastrada.", contar_grupos(qs, "criticidade"), Criticidade.choices, "Sem achados para os filtros selecionados."),
            grafico("Achados por categoria", "Categoria textual do achado.", [Serie(chave or "Sem categoria", quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(qs, "categoria") if quantidade], "Sem achados para os filtros selecionados."),
            grafico(
                "Materialidade",
                "Soma da materialidade financeira informada, por criticidade. Criticidade sem valor permanece fora da soma.",
                _materialidade_por_criticidade(qs),
                "Sem materialidade informada no recorte.",
            ),
        ],
        colunas=["Código", "Título", "Status", "Criticidade", "Materialidade", "Prestação"],
        linhas=[
            Linha(
                [
                    item.codigo,
                    item.titulo,
                    item.get_status_display(),
                    item.get_criticidade_display(),
                    texto_decimal(item.materialidade_financeira),
                    item.prestacao_contas.numero_processo,
                ],
                reverse("achados:detalhe", kwargs={"pk": item.pk}),
            )
            for item in qs.select_related("prestacao_contas")[:80]
        ],
        vazio_tabela="Sem achados para os filtros selecionados.",
        avisos=_aviso(qs),
    )


def _materialidade_por_criticidade(qs) -> list[Serie]:
    from django.db.models import Sum

    linhas = qs.values("criticidade").annotate(total=Sum("materialidade_financeira")).order_by("criticidade")
    series = []
    for linha in linhas:
        if linha["total"] is None:
            continue
        series.append(Serie(_rotulo(Criticidade.choices, linha["criticidade"]), int((linha["total"] * 100).to_integral_value()), texto_decimal(linha["total"])))
    return series


def montar_pre_analise(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.pareceres.models import AfirmacaoPreAnalise

    qs = pre_analises(filtros)
    afirmacoes = AfirmacaoPreAnalise.objects.filter(secao__pre_analise__in=qs)
    return PainelAba(
        kpis=[
            _kpi("Pré-análises", texto_contagem(qs.count())),
            _kpi("Aguardando revisão", texto_contagem(qs.filter(status=StatusPreAnalise.AGUARDANDO_REVISAO).count())),
            _kpi("Congeladas", texto_contagem(qs.filter(status=StatusPreAnalise.CONGELADA).count())),
            _kpi("Versões", texto_contagem(qs.count()), observacao="Cada versão é um registro. Não há parecer conclusivo."),
            _kpi("Afirmações determinísticas", texto_contagem(afirmacoes.filter(origem_conteudo=OrigemConteudo.DETERMINISTICO).count())),
            _kpi("Afirmações redigidas por IA", texto_contagem(afirmacoes.filter(origem_conteudo=OrigemConteudo.IA).count())),
            _kpi("Afirmações alteradas por humano", texto_contagem(afirmacoes.filter(origem_conteudo=OrigemConteudo.HUMANO).count())),
            _kpi("Afirmações rejeitadas", texto_contagem(afirmacoes.filter(status_validacao="rejeitada").count())),
            _kpi("Com limitação registrada", texto_contagem(qs.exclude(limitacoes="").count())),
        ],
        graficos=[
            _por_choices("Pré-análises por status", "Status da versão. Congelada não é decisão administrativa.", contar_grupos(qs, "status"), StatusPreAnalise.choices, "Sem pré-análises para os filtros selecionados."),
            _por_choices("Origem das afirmações", "Origem gravada na afirmação: determinístico, IA ou humano.", contar_grupos(afirmacoes, "origem_conteudo"), OrigemConteudo.choices, "Sem afirmações no recorte."),
            _por_choices("Encaminhamentos", "Encaminhamento sugerido. Não aprova nem reprova a prestação.", contar_grupos(qs, "encaminhamento"), EncaminhamentoPreAnalise.choices, "Sem encaminhamento no recorte."),
        ],
        colunas=["Código", "Versão", "Status", "Prestação"],
        linhas=[
            Linha([item.codigo, str(item.versao), item.get_status_display(), item.prestacao_contas.numero_processo], reverse("pareceres:detalhe", kwargs={"pk": item.pk}))
            for item in qs.select_related("prestacao_contas")[:80]
        ],
        vazio_tabela="Sem pré-análises para os filtros selecionados.",
        avisos=_aviso(qs) + ["A pré-análise não declara a prestação regular ou irregular."],
    )


def montar_revisao(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.achados.models import RevisaoAchado
    from aplicacao.avaliacao.models import RevisaoCorrespondencia
    from aplicacao.pareceres.models import RevisaoPreAnalise
    from aplicacao.usuarios.models import Usuario

    achado_rev = RevisaoAchado.objects.all()
    pre_rev = RevisaoPreAnalise.objects.all()
    corr_rev = RevisaoCorrespondencia.objects.all()
    if filtros.prestacao:
        achado_rev = achado_rev.filter(achado__prestacao_contas_id=filtros.prestacao)
        pre_rev = pre_rev.filter(pre_analise__prestacao_contas_id=filtros.prestacao)
        corr_rev = corr_rev.filter(correspondencia__avaliacao__prestacao_contas_id=filtros.prestacao)
    if filtros.inicio:
        achado_rev = achado_rev.filter(data_hora__date__gte=filtros.inicio)
        pre_rev = pre_rev.filter(data_hora__date__gte=filtros.inicio)
        corr_rev = corr_rev.filter(data_hora__date__gte=filtros.inicio)
    if filtros.fim:
        achado_rev = achado_rev.filter(data_hora__date__lte=filtros.fim)
        pre_rev = pre_rev.filter(data_hora__date__lte=filtros.fim)
        corr_rev = corr_rev.filter(data_hora__date__lte=filtros.fim)
    if filtros.responsavel:
        achado_rev = achado_rev.filter(usuario_id=filtros.responsavel)
        pre_rev = pre_rev.filter(usuario_id=filtros.responsavel)
        corr_rev = corr_rev.filter(usuario_id=filtros.responsavel)
    usuarios = set(achado_rev.values_list("usuario_id", flat=True)) | set(pre_rev.values_list("usuario_id", flat=True)) | set(corr_rev.values_list("usuario_id", flat=True))
    usuarios.discard(None)
    delta = achado_rev.annotate(
        decorrido=ExpressionWrapper(F("data_hora") - F("achado__criado_em"), output_field=DurationField())
    ).aggregate(media=Avg("decorrido"))["media"]
    horas = None if delta is None else Decimal(str(delta.total_seconds())) / Decimal(3600)
    return PainelAba(
        kpis=[
            _kpi("Intervenções", texto_contagem(achado_rev.count() + pre_rev.count() + corr_rev.count())),
            _kpi("Usuários envolvidos", texto_contagem(len(usuarios))),
            _kpi("Auditores", texto_contagem(Usuario.objects.filter(pk__in=usuarios, perfil=Usuario.Perfil.AUDITOR).count())),
            _kpi("Analistas", texto_contagem(Usuario.objects.filter(pk__in=usuarios, perfil=Usuario.Perfil.ANALISTA).count())),
            _kpi("Aceitações de achado", texto_contagem(achado_rev.filter(acao="confirmar").count())),
            _kpi("Rejeições de achado", texto_contagem(achado_rev.filter(acao="descartar").count())),
            _kpi("Ajustes de achado", texto_contagem(achado_rev.filter(acao="ajustar").count())),
            _kpi("Revisões de pré-análise", texto_contagem(pre_rev.count())),
            _kpi("Revisões de correspondência", texto_contagem(corr_rev.count())),
            _kpi("Tempo decorrido médio até a revisão do achado (horas)", texto_decimal(horas), observacao="Tempo entre a criação do achado e a revisão. Não é tempo de trabalho humano."),
        ],
        graficos=[],
        colunas=["Tipo", "Ação", "Quando", "Usuário"],
        linhas=_linhas_revisao(achado_rev, pre_rev, corr_rev),
        vazio_tabela="Sem intervenções humanas no recorte.",
    )


def _linhas_revisao(achado_rev, pre_rev, corr_rev) -> list[Linha]:
    linhas = []
    for item in achado_rev.select_related("usuario", "achado")[:30]:
        linhas.append(Linha(["Achado", item.get_acao_display(), item.data_hora.strftime("%d/%m/%Y %H:%M"), getattr(item.usuario, "username", "")], reverse("achados:detalhe", kwargs={"pk": item.achado_id})))
    for item in pre_rev.select_related("usuario")[:20]:
        linhas.append(Linha(["Pré-análise", item.acao, item.data_hora.strftime("%d/%m/%Y %H:%M"), getattr(item.usuario, "username", "")], reverse("pareceres:detalhe", kwargs={"pk": item.pre_analise_id})))
    for item in corr_rev.select_related("usuario", "correspondencia")[:20]:
        linhas.append(Linha(["Correspondência", item.acao, item.data_hora.strftime("%d/%m/%Y %H:%M"), getattr(item.usuario, "username", "")], reverse("avaliacao:detalhe", kwargs={"pk": item.correspondencia.avaliacao_id})))
    return linhas


def montar_ia_tecnico(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.avaliacao.models import ComparacaoRegra, CorrespondenciaAchado, GroundTruthPrestacao

    qs = avaliacoes(filtros)
    correspondencias = CorrespondenciaAchado.objects.filter(avaliacao__in=qs)
    tp = correspondencias.filter(classificacao=ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO).count()
    fp = correspondencias.filter(classificacao=ClassificacaoCorrespondencia.FALSO_POSITIVO).count()
    fn = correspondencias.filter(classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO).count()
    parciais = correspondencias.filter(classificacao=ClassificacaoCorrespondencia.CORRESPONDENCIA_PARCIAL).count()
    pendentes = correspondencias.filter(classificacao=ClassificacaoCorrespondencia.PENDENTE_REVISAO).count()
    fn_criticos = correspondencias.filter(
        classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO,
        ground_truth_achado__criticidade__in=[CriticidadeReferencia.ALTA, CriticidadeReferencia.CRITICA],
    )
    materialidade = somar(fn_criticos, "ground_truth_achado__materialidade") if False else _soma_materialidade_fn(fn_criticos)
    gts = GroundTruthPrestacao.objects.filter(avaliacoes__in=qs).distinct()
    if filtros.origem == "demonstracao":
        gts = gts.filter(dados_demonstracao=True)
    elif filtros.origem == "operacional":
        gts = gts.filter(dados_demonstracao=False)
    comparacoes = ComparacaoRegra.objects.filter(avaliacao__in=qs, aplicabilidade="avaliavel")
    return PainelAba(
        kpis=[
            _kpi("Avaliações", texto_contagem(qs.count()), reverse("avaliacao:lista")),
            _kpi("Ground Truths vinculados", texto_contagem(gts.count())),
            _kpi("Verdadeiros positivos", texto_contagem(tp)),
            _kpi("Falsos positivos", texto_contagem(fp)),
            _kpi("Falsos negativos", texto_contagem(fn)),
            _kpi("Correspondências parciais", texto_contagem(parciais)),
            _kpi("Pendências", texto_contagem(pendentes)),
            _kpi("Precisão", taxa(tp, tp + fp), observacao="TP / (TP + FP) das correspondências do recorte. Denominador zero permanece não disponível."),
            _kpi("Recall", taxa(tp, tp + fn)),
            _kpi("F1", _f1(tp, fp, fn)),
            _kpi("Falsos negativos críticos", texto_contagem(fn_criticos.count())),
            _kpi("Materialidade dos falsos negativos críticos", texto_decimal(materialidade), observacao="Soma somente materialidades existentes."),
        ],
        graficos=[
            grafico("Matriz IA × técnico", "Contagens de correspondência. Parcial e pendente ficam de fora de precisão e recall.", [Serie(rotulo, quantidade, texto_contagem(quantidade)) for rotulo, quantidade in (("Verdadeiro positivo", tp), ("Falso positivo", fp), ("Falso negativo", fn), ("Parcial", parciais), ("Pendente", pendentes)) if quantidade], "Sem avaliações disponíveis."),
            grafico(
                "Desempenho por categoria de regra",
                "Concordância apenas entre comparações avaliáveis. Sem Ground Truth ou fora de escopo não entram no denominador.",
                _concordancia_por(comparacoes, "regra__categoria"),
                "Sem comparações avaliáveis no recorte.",
            ),
            grafico(
                "Desempenho por tipo de execução",
                "Mesma regra de denominador da comparação de regras.",
                _concordancia_por(comparacoes, "regra__tipo_execucao"),
                "Sem comparações avaliáveis no recorte.",
            ),
        ],
        colunas=["Avaliação", "Versão", "Status", "Precisão", "Recall", "Prestação"],
        linhas=[
            Linha(
                [
                    item.codigo,
                    str(item.versao),
                    item.get_status_display(),
                    _metrica_gravada(item, "precisao"),
                    _metrica_gravada(item, "recall"),
                    item.prestacao_contas.numero_processo,
                ],
                reverse("avaliacao:detalhe", kwargs={"pk": item.pk}),
            )
            for item in qs.select_related("prestacao_contas")[:40]
        ],
        vazio_tabela="Sem avaliações disponíveis.",
        avisos=_aviso(qs, "dados_demonstracao") + ["Não há nota geral da IA. Precisão, recall e F1 permanecem separados."],
    )


def _soma_materialidade_fn(qs):
    from django.db.models import Sum

    return qs.aggregate(total=Sum("ground_truth_achado__materialidade"))["total"]


def _f1(tp: int, fp: int, fn: int) -> str:
    precisao = None if tp + fp == 0 else Decimal(tp) / Decimal(tp + fp)
    recall = None if tp + fn == 0 else Decimal(tp) / Decimal(tp + fn)
    if precisao is None or recall is None or precisao + recall == 0:
        return NAO_DISPONIVEL
    return texto_decimal((Decimal(2) * precisao * recall) / (precisao + recall), Decimal("0.0001"))


def _metrica_gravada(avaliacao, chave: str) -> str:
    valor = (avaliacao.metricas or {}).get(chave)
    if valor in (None, ""):
        return NAO_DISPONIVEL
    return str(valor)


def _concordancia_por(comparacoes, campo: str) -> list[Serie]:
    linhas = comparacoes.values(campo).annotate(
        avaliaveis=Count("id"),
        concordantes=Count("id", filter=Q(concordante=True)),
    )
    series = []
    for linha in linhas:
        taxa_txt = taxa(linha["concordantes"], linha["avaliaveis"])
        rotulo = linha[campo] or "Sem categoria"
        series.append(Serie(str(rotulo), linha["avaliaveis"], taxa_txt))
    return series


def montar_operacao(filtros: FiltrosPainel) -> PainelAba:
    from aplicacao.inteligencia_artificial.models import ModeloInteligenciaArtificial, PromptInteligenciaArtificial, UsoInteligenciaArtificial, VersaoPromptInteligenciaArtificial

    qs = usos(filtros)
    return PainelAba(
        kpis=[
            _kpi("Modelos cadastrados", texto_contagem(ModeloInteligenciaArtificial.objects.count())),
            _kpi("Modelos ativos", texto_contagem(ModeloInteligenciaArtificial.objects.filter(ativo=True).count())),
            _kpi("Prompts", texto_contagem(PromptInteligenciaArtificial.objects.count())),
            _kpi("Versões de prompt", texto_contagem(VersaoPromptInteligenciaArtificial.objects.count())),
            _kpi("Execuções", texto_contagem(qs.count())),
            _kpi("Sucessos", texto_contagem(qs.filter(status="sucesso").count())),
            _kpi("Erros controlados", texto_contagem(qs.filter(status="erro_controlado").count())),
            _kpi("Limite excedido", texto_contagem(qs.filter(status="limite_excedido").count())),
            _kpi("Tokens de entrada", texto_contagem(int(somar(qs, "tokens_entrada") or 0)) if qs.exists() else NAO_DISPONIVEL, observacao="Soma dos tokens gravados. Sem chamadas, o indicador fica não disponível, e não zero."),
            _kpi("Tokens de saída", texto_contagem(int(somar(qs, "tokens_saida") or 0)) if qs.exists() else NAO_DISPONIVEL),
            _kpi("Tokens totais", texto_contagem(int(somar(qs, "tokens_total") or 0)) if qs.exists() else NAO_DISPONIVEL),
            _kpi("Latência média (ms)", texto_decimal(_media_duracao(qs), Decimal("1")), observacao="Média de duracao_ms das chamadas do recorte."),
            _kpi("Sem telemetria de tokens", texto_contagem(qs.filter(tokens_total=0, tokens_entrada=0, tokens_saida=0).count()), observacao="O campo de token não aceita nulo. Zero aqui significa telemetria não registrada."),
        ],
        graficos=[
            grafico("Execuções por provedor", "Provedor gravado na chamada. A chave não é exibida.", [Serie(chave or "Não informado", quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(qs, "provedor") if quantidade], "Sem execuções de IA no recorte."),
            grafico("Execuções por agente", "Agente gravado na chamada.", [Serie(chave or "Não informado", quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(qs, "agente") if quantidade], "Sem execuções de IA no recorte."),
            grafico("Status das chamadas", "Status operacional registrado.", [Serie(chave or "Não informado", quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(qs, "status") if quantidade], "Sem execuções de IA no recorte."),
            grafico("Erros normalizados", "Código normalizado do erro. Não inclui prompt nem resposta.", [Serie(chave, quantidade, texto_contagem(quantidade)) for chave, quantidade in contar_grupos(qs.exclude(erro_normalizado=""), "erro_normalizado") if quantidade], "Sem erro normalizado no recorte."),
        ],
        colunas=["Agente", "Provedor", "Status", "Tokens", "Quando"],
        linhas=[
            Linha(
                [item.agente, item.provedor, item.get_status_display(), texto_contagem(item.tokens_total), item.iniciada_em.strftime("%d/%m/%Y %H:%M")],
                reverse("ia:consumo"),
            )
            for item in qs.order_by("-iniciada_em")[:40]
        ],
        vazio_tabela="Sem execuções de IA no recorte.",
        avisos=["Prompts, chaves, autorizações e respostas não são exibidos nesta aba."],
    )


def _media_duracao(qs):
    from django.db.models import Avg

    if not qs.exists():
        return None
    return qs.aggregate(media=Avg("duracao_ms"))["media"]
