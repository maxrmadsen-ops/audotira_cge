from django.conf import settings
from django.db import models

from aplicacao.avaliacao.escolhas import (
    AcaoRevisaoCorrespondencia,
    AplicabilidadeComparacao,
    ClassificacaoCorrespondencia,
    CriticidadeReferencia,
    MetodoCorrespondencia,
    ModoGroundTruth,
    PrioridadeReferencia,
    SituacaoReferencia,
    StatusAvaliacao,
    StatusGroundTruth,
)


class GroundTruthPrestacao(models.Model):
    """Referência técnica independente. Não alimenta a geração da análise."""

    codigo = models.CharField("código", max_length=20)
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="ground_truths",
    )
    versao = models.PositiveIntegerField("versão", default=1)
    versao_registro = models.PositiveIntegerField("versão do registro", default=1)
    modo = models.CharField("modo", max_length=20, choices=ModoGroundTruth.choices)
    status = models.CharField(
        "status",
        max_length=20,
        choices=StatusGroundTruth.choices,
        default=StatusGroundTruth.RASCUNHO,
    )
    responsavel_tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável técnico",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ground_truths_responsavel",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ground_truths_criados",
    )
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ground_truths_validados",
    )
    congelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="congelado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ground_truths_congelados",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    validado_em = models.DateTimeField("validado em", null=True, blank=True)
    congelado_em = models.DateTimeField("congelado em", null=True, blank=True)
    observacoes = models.TextField("observações", blank=True)
    hash_conteudo = models.CharField("hash do conteúdo", max_length=64, blank=True)
    dados_demonstracao = models.BooleanField("dados de demonstração", default=False)

    class Meta:
        verbose_name = "Ground Truth da prestação"
        verbose_name_plural = "Ground Truth das prestações"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["codigo", "versao"], name="ground_truth_codigo_versao_unico"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} v{self.versao}"

    @property
    def congelado(self) -> bool:
        return self.status == StatusGroundTruth.CONGELADO


class GroundTruthRegra(models.Model):
    """Resultado de referência de uma versão de regra. Categorias diferentes não são fundidas."""

    ground_truth = models.ForeignKey(
        GroundTruthPrestacao,
        verbose_name="Ground Truth",
        on_delete=models.CASCADE,
        related_name="regras_referencia",
    )
    regra = models.ForeignKey(
        "regras.RegraAnalise",
        verbose_name="regra",
        on_delete=models.PROTECT,
        related_name="referencias_ground_truth",
    )
    aplicavel = models.BooleanField("aplicável", default=True)
    resultado_esperado = models.CharField("resultado esperado", max_length=120)
    justificativa = models.TextField("justificativa", blank=True)
    observacao = models.TextField("observação", blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referencias_regra_ground_truth",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Ground Truth da regra"
        verbose_name_plural = "Ground Truth das regras"
        constraints = [
            models.UniqueConstraint(fields=["ground_truth", "regra"], name="ground_truth_regra_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.regra.codigo} · {self.resultado_esperado}"


class GroundTruthAchado(models.Model):
    """Achado de referência com fato, evidência, regra e norma. Não é texto livre isolado."""

    codigo = models.CharField("código", max_length=20)
    ground_truth = models.ForeignKey(
        GroundTruthPrestacao,
        verbose_name="Ground Truth",
        on_delete=models.CASCADE,
        related_name="achados_referencia",
    )
    categoria = models.CharField("categoria", max_length=80, blank=True)
    titulo = models.CharField("título", max_length=300)
    descricao = models.TextField("descrição", blank=True)
    fato = models.TextField("fato", blank=True)
    materialidade = models.DecimalField("materialidade", max_digits=16, decimal_places=2, null=True, blank=True)
    criticidade = models.CharField(
        "criticidade",
        max_length=20,
        choices=CriticidadeReferencia.choices,
        default=CriticidadeReferencia.BAIXA,
    )
    prioridade = models.CharField(
        "prioridade",
        max_length=20,
        choices=PrioridadeReferencia.choices,
        default=PrioridadeReferencia.NORMAL,
    )
    situacao = models.CharField(
        "situação",
        max_length=30,
        choices=SituacaoReferencia.choices,
        default=SituacaoReferencia.REGISTRADO,
    )
    observacao_tecnica = models.TextField("observação técnica", blank=True)
    regras = models.ManyToManyField("regras.RegraAnalise", blank=True, related_name="achados_ground_truth", verbose_name="regras")
    evidencias = models.ManyToManyField("achados.Evidencia", blank=True, related_name="achados_ground_truth", verbose_name="evidências")
    documentos = models.ManyToManyField("documentos.Documento", blank=True, related_name="achados_ground_truth", verbose_name="documentos")
    normas = models.ManyToManyField("normas.Norma", blank=True, related_name="achados_ground_truth", verbose_name="normas")
    trechos = models.ManyToManyField(
        "normas.TrechoNormativo",
        blank=True,
        related_name="achados_ground_truth",
        verbose_name="trechos normativos",
    )
    pessoas = models.ManyToManyField("entidades.Pessoa", blank=True, related_name="achados_ground_truth", verbose_name="pessoas")
    despesas = models.ManyToManyField(
        "prestacoes_contas.Despesa",
        blank=True,
        related_name="achados_ground_truth",
        verbose_name="despesas",
    )
    pagamentos = models.ManyToManyField(
        "prestacoes_contas.Pagamento",
        blank=True,
        related_name="achados_ground_truth",
        verbose_name="pagamentos",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="achados_ground_truth_criados",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    dados_demonstracao = models.BooleanField("dados de demonstração", default=False)

    class Meta:
        verbose_name = "achado de Ground Truth"
        verbose_name_plural = "achados de Ground Truth"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(fields=["ground_truth", "codigo"], name="ground_truth_achado_codigo_unico"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.titulo}"


class SnapshotAvaliacao(models.Model):
    """Estado imutável da análise avaliada. Não copia o documento integral."""

    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="snapshots_avaliacao",
    )
    execucao_analise = models.ForeignKey(
        "regras.ExecucaoAnalise",
        verbose_name="execução da análise",
        on_delete=models.PROTECT,
        related_name="snapshots_avaliacao",
    )
    pre_analise = models.ForeignKey(
        "pareceres.PreAnaliseTecnica",
        verbose_name="pré-análise",
        on_delete=models.PROTECT,
        related_name="snapshots_avaliacao",
    )
    versao_pre_analise = models.PositiveIntegerField("versão da pré-análise")
    hash_pre_analise = models.CharField("hash da pré-análise", max_length=64)
    congelamento_pre_analise = models.DateTimeField("congelamento da pré-análise", null=True, blank=True)
    referencias = models.JSONField("referências", default=dict, blank=True)
    criado_em = models.DateTimeField("data e hora", auto_now_add=True)
    hash_conteudo = models.CharField("hash do instantâneo", max_length=64, blank=True)

    class Meta:
        verbose_name = "instantâneo da avaliação"
        verbose_name_plural = "instantâneos da avaliação"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Instantâneo {self.pk} · {self.pre_analise_id}"


class AvaliacaoInteligenciaArtificial(models.Model):
    """Comparação rastreável. Uma versão congelada não é recalculada."""

    codigo = models.CharField("código", max_length=20)
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="avaliacoes_ia",
    )
    snapshot = models.ForeignKey(
        SnapshotAvaliacao,
        verbose_name="instantâneo",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="avaliacoes",
    )
    ground_truth = models.ForeignKey(
        GroundTruthPrestacao,
        verbose_name="Ground Truth",
        on_delete=models.PROTECT,
        related_name="avaliacoes",
    )
    avaliacao_anterior = models.ForeignKey(
        "self",
        verbose_name="versão anterior",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="versoes_seguintes",
    )
    versao = models.PositiveIntegerField("versão", default=1)
    versao_registro = models.PositiveIntegerField("versão do registro", default=1)
    status = models.CharField("status", max_length=30, choices=StatusAvaliacao.choices, default=StatusAvaliacao.PREPARANDO)
    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="iniciado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="avaliacoes_iniciadas",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="avaliacoes_revisadas",
    )
    congelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="congelado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="avaliacoes_congeladas",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    concluido_em = models.DateTimeField("concluído em", null=True, blank=True)
    congelado_em = models.DateTimeField("congelado em", null=True, blank=True)
    hash_conteudo = models.CharField("hash do conteúdo", max_length=64, blank=True)
    observacoes = models.TextField("observações", blank=True)
    metricas = models.JSONField("métricas", default=dict, blank=True)
    erro = models.CharField("erro", max_length=300, blank=True)
    dados_demonstracao = models.BooleanField("dados de demonstração", default=False)

    class Meta:
        verbose_name = "avaliação IA × técnico"
        verbose_name_plural = "avaliações IA × técnico"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["codigo", "versao"], name="avaliacao_codigo_versao_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} v{self.versao}"

    @property
    def congelada(self) -> bool:
        return self.status == StatusAvaliacao.CONGELADA


class ComparacaoRegra(models.Model):
    avaliacao = models.ForeignKey(
        AvaliacaoInteligenciaArtificial,
        verbose_name="avaliação",
        on_delete=models.CASCADE,
        related_name="comparacoes_regra",
    )
    regra = models.ForeignKey("regras.RegraAnalise", verbose_name="regra", on_delete=models.PROTECT, related_name="comparacoes_avaliacao")
    execucao_regra = models.ForeignKey(
        "regras.ExecucaoRegra",
        verbose_name="execução da regra",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="comparacoes_avaliacao",
    )
    ground_truth_regra = models.ForeignKey(
        GroundTruthRegra,
        verbose_name="Ground Truth da regra",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="comparacoes",
    )
    versao_regra = models.PositiveIntegerField("versão da regra", default=1)
    resultado_sistema = models.CharField("resultado do sistema", max_length=120, blank=True)
    resultado_ground_truth = models.CharField("resultado do Ground Truth", max_length=120, blank=True)
    aplicabilidade = models.CharField("aplicabilidade", max_length=30, choices=AplicabilidadeComparacao.choices)
    concordante = models.BooleanField("concordante", null=True, blank=True)
    motivo = models.CharField("motivo", max_length=200, blank=True)
    criada_em = models.DateTimeField("data da comparação", auto_now_add=True)

    class Meta:
        verbose_name = "comparação de regra"
        verbose_name_plural = "comparações de regra"
        constraints = [
            models.UniqueConstraint(fields=["avaliacao", "regra"], name="comparacao_regra_unica"),
        ]


class CorrespondenciaAchado(models.Model):
    avaliacao = models.ForeignKey(
        AvaliacaoInteligenciaArtificial,
        verbose_name="avaliação",
        on_delete=models.CASCADE,
        related_name="correspondencias",
    )
    achado = models.ForeignKey(
        "achados.Achado",
        verbose_name="achado da solução",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correspondencias_avaliacao",
    )
    ground_truth_achado = models.ForeignKey(
        GroundTruthAchado,
        verbose_name="achado de Ground Truth",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correspondencias",
    )
    classificacao = models.CharField("classificação", max_length=30, choices=ClassificacaoCorrespondencia.choices)
    metodo = models.CharField(
        "método",
        max_length=30,
        choices=MetodoCorrespondencia.choices,
        default=MetodoCorrespondencia.DETERMINISTICO,
    )
    confianca = models.DecimalField("confiança", max_digits=6, decimal_places=4, null=True, blank=True)
    justificativa = models.TextField("justificativa", blank=True)
    revisao_humana_necessaria = models.BooleanField("revisão humana necessária", default=False)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="correspondencias_revisadas",
    )
    revisado_em = models.DateTimeField("revisado em", null=True, blank=True)
    observacao = models.TextField("observação", blank=True)

    class Meta:
        verbose_name = "correspondência de achado"
        verbose_name_plural = "correspondências de achado"


class RevisaoCorrespondencia(models.Model):
    correspondencia = models.ForeignKey(
        CorrespondenciaAchado,
        verbose_name="correspondência",
        on_delete=models.CASCADE,
        related_name="revisoes",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revisoes_correspondencia",
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)
    acao = models.CharField("ação", max_length=20, choices=AcaoRevisaoCorrespondencia.choices)
    classificacao_anterior = models.CharField("classificação anterior", max_length=30)
    classificacao_posterior = models.CharField("classificação posterior", max_length=30)
    justificativa = models.TextField("justificativa", blank=True)
    observacao = models.TextField("observação", blank=True)

    class Meta:
        verbose_name = "revisão de correspondência"
        verbose_name_plural = "revisões de correspondência"
        ordering = ["-data_hora"]
