from django.conf import settings
from django.db import models

from aplicacao.pareceres.escolhas import (
    AcaoRevisaoPreAnalise,
    EncaminhamentoPreAnalise,
    OrigemConteudo,
    StatusPreAnalise,
    StatusValidacaoAfirmacao,
    TipoAfirmacao,
    TipoSecao,
)


class PreAnaliseTecnica(models.Model):
    """Documento técnico versionado. A revisão humana não é Ground Truth."""

    codigo = models.CharField("código", max_length=20, unique=True)
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="pre_analises",
    )
    execucao_analise = models.ForeignKey(
        "regras.ExecucaoAnalise",
        verbose_name="execução da análise",
        on_delete=models.PROTECT,
        related_name="pre_analises",
    )
    versao = models.PositiveIntegerField("versão")
    versao_registro = models.PositiveIntegerField("versão do registro", default=1)
    status = models.CharField("status", max_length=30, choices=StatusPreAnalise.choices, default=StatusPreAnalise.RASCUNHO)
    titulo = models.CharField("título", max_length=300)
    resumo_executivo = models.TextField("resumo executivo", blank=True)
    escopo = models.TextField("escopo", blank=True)
    limitacoes = models.TextField("limitações", blank=True)
    encaminhamento = models.CharField(
        "encaminhamento",
        max_length=40,
        choices=EncaminhamentoPreAnalise.choices,
        default=EncaminhamentoPreAnalise.SUBMETER_AO_AUDITOR,
    )
    modelo_inteligencia_artificial = models.ForeignKey(
        "inteligencia_artificial.ModeloInteligenciaArtificial",
        verbose_name="modelo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pre_analises",
    )
    versao_prompt = models.ForeignKey(
        "inteligencia_artificial.VersaoPromptInteligenciaArtificial",
        verbose_name="versão do prompt",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pre_analises",
    )
    provedor = models.CharField("provedor", max_length=40, blank=True)
    solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="solicitada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pre_analises_solicitadas",
    )
    gerada_em = models.DateTimeField("gerada em", null=True, blank=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pre_analises_revisadas",
    )
    revisada_em = models.DateTimeField("revisada em", null=True, blank=True)
    congelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="congelada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pre_analises_congeladas",
    )
    congelada_em = models.DateTimeField("congelada em", null=True, blank=True)
    hash_conteudo = models.CharField("hash do conteúdo", max_length=64, blank=True)
    diagnostico_ia = models.JSONField("diagnóstico da IA", default=dict, blank=True)
    demonstracao = models.BooleanField("demonstração", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pré-análise técnica"
        verbose_name_plural = "pré-análises técnicas"
        ordering = ["-versao", "-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["prestacao_contas", "execucao_analise", "versao"], name="pre_analise_versao_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} v{self.versao}"

    @property
    def congelada(self) -> bool:
        return self.status == StatusPreAnalise.CONGELADA


class SecaoPreAnalise(models.Model):
    pre_analise = models.ForeignKey(PreAnaliseTecnica, verbose_name="pré-análise", on_delete=models.CASCADE, related_name="secoes")
    tipo = models.CharField("tipo", max_length=40, choices=TipoSecao.choices)
    ordem = models.PositiveIntegerField("ordem")
    titulo = models.CharField("título", max_length=200)
    origem_conteudo = models.CharField(
        "origem do conteúdo",
        max_length=20,
        choices=OrigemConteudo.choices,
        default=OrigemConteudo.DETERMINISTICO,
    )

    class Meta:
        verbose_name = "seção da pré-análise"
        verbose_name_plural = "seções da pré-análise"
        ordering = ["ordem"]
        constraints = [
            models.UniqueConstraint(fields=["pre_analise", "tipo"], name="secao_pre_analise_unica"),
        ]


class AfirmacaoPreAnalise(models.Model):
    secao = models.ForeignKey(SecaoPreAnalise, verbose_name="seção", on_delete=models.CASCADE, related_name="afirmacoes")
    ordem = models.PositiveIntegerField("ordem")
    tipo = models.CharField("tipo", max_length=30, choices=TipoAfirmacao.choices)
    texto_original_ia = models.TextField("texto original da IA", blank=True)
    texto_atual = models.TextField("texto atual")
    status_validacao = models.CharField(
        "status de validação",
        max_length=30,
        choices=StatusValidacaoAfirmacao.choices,
        default=StatusValidacaoAfirmacao.VALIDADA,
    )
    origem_conteudo = models.CharField(
        "origem do conteúdo",
        max_length=20,
        choices=OrigemConteudo.choices,
        default=OrigemConteudo.DETERMINISTICO,
    )
    exibir_oficial = models.BooleanField("exibir na versão oficial", default=True)
    alterada_por_humano = models.BooleanField("alterada por humano", default=False)
    motivo_rejeicao = models.CharField("motivo da rejeição", max_length=300, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "afirmação da pré-análise"
        verbose_name_plural = "afirmações da pré-análise"
        ordering = ["ordem"]


class FonteAfirmacaoPreAnalise(models.Model):
    afirmacao = models.ForeignKey(AfirmacaoPreAnalise, verbose_name="afirmação", on_delete=models.CASCADE, related_name="fontes")
    codigo_fonte = models.CharField("código da fonte", max_length=80)
    tipo_fonte = models.CharField("tipo da fonte", max_length=40)
    evidencia = models.ForeignKey("achados.Evidencia", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    achado = models.ForeignKey("achados.Achado", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    regra = models.ForeignKey("regras.RegraAnalise", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    execucao_regra = models.ForeignKey("regras.ExecucaoRegra", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    norma = models.ForeignKey("normas.Norma", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    trecho_normativo = models.ForeignKey("normas.TrechoNormativo", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    documento = models.ForeignKey("documentos.Documento", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    pagina = models.PositiveIntegerField("página", null=True, blank=True)
    calculo = models.ForeignKey("regras.CalculoExecucaoRegra", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")
    revisao_achado = models.ForeignKey("achados.RevisaoAchado", null=True, blank=True, on_delete=models.PROTECT, related_name="fontes_pre_analise")

    class Meta:
        verbose_name = "fonte da afirmação"
        verbose_name_plural = "fontes da afirmação"


class RevisaoPreAnalise(models.Model):
    """Decisão operacional humana. Não constitui Ground Truth."""

    pre_analise = models.ForeignKey(PreAnaliseTecnica, verbose_name="pré-análise", on_delete=models.CASCADE, related_name="revisoes")
    afirmacao = models.ForeignKey(AfirmacaoPreAnalise, null=True, blank=True, on_delete=models.CASCADE, related_name="revisoes")
    acao = models.CharField("ação", max_length=30, choices=AcaoRevisaoPreAnalise.choices)
    texto_anterior = models.TextField("texto anterior", blank=True)
    texto_posterior = models.TextField("texto posterior", blank=True)
    justificativa = models.TextField("justificativa", blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revisoes_pre_analise",
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)

    class Meta:
        verbose_name = "revisão da pré-análise"
        verbose_name_plural = "revisões da pré-análise"
        ordering = ["-data_hora"]
