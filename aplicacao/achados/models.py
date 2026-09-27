from django.conf import settings
from django.db import models

from aplicacao.achados.escolhas import (
    AcaoRevisao,
    ConfiabilidadeOrigem,
    Criticidade,
    MetodoObtencao,
    NaturezaAchado,
    OrigemGeracao,
    PapelEvidencia,
    Prioridade,
    StatusAchado,
    StatusValidacaoEvidencia,
    TipoConstatacao,
    TipoEvidencia,
)


class Evidencia(models.Model):
    """Fato rastreável. Pode existir sem achado."""

    codigo = models.CharField("código", max_length=20, unique=True)
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    tipo = models.CharField("tipo", max_length=20, choices=TipoEvidencia.choices)
    origem = models.CharField("origem", max_length=40, blank=True)
    documento = models.ForeignKey(
        "documentos.Documento",
        verbose_name="documento",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    pagina_documento = models.ForeignKey(
        "documentos.PaginaDocumento",
        verbose_name="página do documento",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    dado_extraido_documento = models.ForeignKey(
        "documentos.DadoExtraidoDocumento",
        verbose_name="dado extraído",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    execucao_regra = models.ForeignKey(
        "regras.ExecucaoRegra",
        verbose_name="execução da regra",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    trecho = models.CharField("trecho", max_length=500, blank=True)
    valor_textual = models.CharField("valor textual", max_length=255, blank=True)
    valor_numerico = models.DecimalField("valor numérico", max_digits=16, decimal_places=4, null=True, blank=True)
    data_referencia = models.DateField("data de referência", null=True, blank=True)
    entidade_referencia = models.CharField("entidade de referência", max_length=200, blank=True)
    hash_origem = models.CharField("hash de origem", max_length=64, blank=True)
    metodo_obtencao = models.CharField("método de obtenção", max_length=20, choices=MetodoObtencao.choices)
    confiabilidade_origem = models.CharField(
        "confiabilidade da origem",
        max_length=20,
        choices=ConfiabilidadeOrigem.choices,
        default=ConfiabilidadeOrigem.NAO_AVALIADA,
    )
    status_validacao = models.CharField(
        "status de validação",
        max_length=20,
        choices=StatusValidacaoEvidencia.choices,
        default=StatusValidacaoEvidencia.PENDENTE,
    )
    operandos = models.JSONField("operandos", default=dict, blank=True)
    uso_inteligencia_artificial = models.ForeignKey(
        "inteligencia_artificial.UsoInteligenciaArtificial",
        verbose_name="uso de inteligência artificial",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    confianca_informada_modelo = models.DecimalField(
        "confiança informada pelo modelo",
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
    )
    demonstracao = models.BooleanField("demonstração", default=False)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evidencias_criadas",
    )
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "evidência"
        verbose_name_plural = "evidências"
        ordering = ["-criada_em"]

    def __str__(self) -> str:
        return self.codigo


class Achado(models.Model):
    """Apontamento potencial. Não é irregularidade confirmada."""

    codigo = models.CharField("código", max_length=20, unique=True)
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="achados",
    )
    analise = models.ForeignKey(
        "regras.ExecucaoAnalise",
        verbose_name="execução da análise",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="achados",
    )
    titulo = models.CharField("título", max_length=300)
    descricao_factual = models.TextField("descrição factual")
    interpretacao = models.TextField("interpretação", blank=True)
    possivel_implicacao = models.TextField("possível implicação", blank=True)
    categoria = models.CharField("categoria", max_length=80, blank=True)
    natureza = models.CharField("natureza", max_length=30, choices=NaturezaAchado.choices, default=NaturezaAchado.OUTRO)
    tipo_constatacao = models.CharField(
        "tipo de constatação",
        max_length=30,
        choices=TipoConstatacao.choices,
        default=TipoConstatacao.ACHADO_POTENCIAL,
    )
    status = models.CharField("status", max_length=30, choices=StatusAchado.choices, default=StatusAchado.POTENCIAL)
    origem_geracao = models.CharField(
        "origem da geração",
        max_length=20,
        choices=OrigemGeracao.choices,
        default=OrigemGeracao.DETERMINISTICA,
    )
    materialidade_financeira = models.DecimalField(
        "materialidade financeira",
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    criticidade = models.CharField("criticidade", max_length=20, choices=Criticidade.choices, default=Criticidade.BAIXA)
    prioridade = models.CharField("prioridade", max_length=20, choices=Prioridade.choices, default=Prioridade.NORMAL)
    requer_analista = models.BooleanField("requer analista", default=True)
    evidencia_insuficiente = models.BooleanField("evidência insuficiente", default=False)
    elementos_rastreaveis = models.BooleanField("elementos rastreáveis", default=False)
    fundamentacao_suficiente = models.BooleanField("fundamentação suficiente", default=False)
    chave_consolidacao = models.CharField("chave de consolidação", max_length=64)
    saida_original = models.JSONField("saída original", default=dict, blank=True)
    sugestao_consolidacao = models.JSONField("sugestão de consolidação", default=dict, blank=True)
    demonstracao = models.BooleanField("demonstração", default=False)
    despesas = models.ManyToManyField("prestacoes_contas.Despesa", blank=True, related_name="achados", verbose_name="despesas")
    documentos_fiscais = models.ManyToManyField(
        "prestacoes_contas.DocumentoFiscal",
        blank=True,
        related_name="achados",
        verbose_name="documentos fiscais",
    )
    pagamentos = models.ManyToManyField("prestacoes_contas.Pagamento", blank=True, related_name="achados", verbose_name="pagamentos")
    pessoas = models.ManyToManyField("entidades.Pessoa", blank=True, related_name="achados", verbose_name="pessoas")
    fornecedores = models.ManyToManyField("entidades.Fornecedor", blank=True, related_name="achados", verbose_name="fornecedores")
    itens_plano = models.ManyToManyField(
        "prestacoes_contas.ItemPlanoTrabalho",
        blank=True,
        related_name="achados",
        verbose_name="itens do plano",
    )
    metas = models.ManyToManyField("prestacoes_contas.Meta", blank=True, related_name="achados", verbose_name="metas")
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "achado"
        verbose_name_plural = "achados"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["analise", "chave_consolidacao"], name="achado_analise_chave_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.titulo}"


class AchadoRegra(models.Model):
    achado = models.ForeignKey(Achado, verbose_name="achado", on_delete=models.CASCADE, related_name="vinculos_regra")
    regra = models.ForeignKey("regras.RegraAnalise", verbose_name="regra", on_delete=models.PROTECT, related_name="achados")
    execucao = models.ForeignKey(
        "regras.ExecucaoRegra",
        verbose_name="execução",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="achados",
    )
    versao_regra = models.PositiveIntegerField("versão da regra", default=1)

    class Meta:
        verbose_name = "regra do achado"
        verbose_name_plural = "regras do achado"
        constraints = [
            models.UniqueConstraint(fields=["achado", "execucao"], name="achado_execucao_unica"),
        ]


class AchadoEvidencia(models.Model):
    achado = models.ForeignKey(Achado, verbose_name="achado", on_delete=models.CASCADE, related_name="vinculos_evidencia")
    evidencia = models.ForeignKey(Evidencia, verbose_name="evidência", on_delete=models.PROTECT, related_name="vinculos")
    papel = models.CharField("papel", max_length=20, choices=PapelEvidencia.choices)

    class Meta:
        verbose_name = "evidência do achado"
        verbose_name_plural = "evidências do achado"
        constraints = [
            models.UniqueConstraint(fields=["achado", "evidencia"], name="achado_evidencia_unica"),
        ]


class Sinalizacao(models.Model):
    """Candidato anterior à consolidação. Não é o achado."""

    analise = models.ForeignKey(
        "regras.ExecucaoAnalise",
        verbose_name="execução da análise",
        on_delete=models.CASCADE,
        related_name="sinalizacoes",
    )
    execucao_regra = models.OneToOneField(
        "regras.ExecucaoRegra",
        verbose_name="execução da regra",
        on_delete=models.CASCADE,
        related_name="sinalizacao",
    )
    achado = models.ForeignKey(
        Achado,
        verbose_name="achado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sinalizacoes",
    )
    chave_consolidacao = models.CharField("chave de consolidação", max_length=64)
    descricao = models.CharField("descrição", max_length=300, blank=True)
    erro = models.CharField("erro", max_length=300, blank=True)
    demonstracao = models.BooleanField("demonstração", default=False)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "sinalização"
        verbose_name_plural = "sinalizações"


class FundamentacaoAchado(models.Model):
    achado = models.ForeignKey(Achado, verbose_name="achado", on_delete=models.CASCADE, related_name="fundamentacoes")
    norma = models.ForeignKey("normas.Norma", verbose_name="norma", on_delete=models.PROTECT, related_name="fundamentacoes_achado")
    trecho_normativo = models.ForeignKey(
        "normas.TrechoNormativo",
        verbose_name="trecho normativo",
        on_delete=models.PROTECT,
        related_name="fundamentacoes_achado",
    )
    papel_fundamento = models.CharField("papel do fundamento", max_length=40, default="elegivel")
    vigencia_inicio = models.DateField("início da vigência aplicada", null=True, blank=True)
    vigencia_fim = models.DateField("fim da vigência aplicada", null=True, blank=True)
    origem_resolucao = models.CharField("origem da resolução", max_length=40, default="resolvedor_normativo")
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "fundamentação do achado"
        verbose_name_plural = "fundamentações do achado"
        constraints = [
            models.UniqueConstraint(fields=["achado", "trecho_normativo"], name="achado_trecho_unico"),
        ]


class RevisaoAchado(models.Model):
    achado = models.ForeignKey(Achado, verbose_name="achado", on_delete=models.CASCADE, related_name="revisoes")
    acao = models.CharField("ação", max_length=30, choices=AcaoRevisao.choices)
    status_anterior = models.CharField("status anterior", max_length=30)
    status_novo = models.CharField("status novo", max_length=30)
    justificativa = models.TextField("justificativa", blank=True)
    comentario = models.TextField("comentário", blank=True)
    valor_anterior = models.JSONField("valor anterior", default=dict, blank=True)
    valor_novo = models.JSONField("valor novo", default=dict, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revisoes_achado",
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)

    class Meta:
        verbose_name = "revisão de achado"
        verbose_name_plural = "revisões de achado"
        ordering = ["-data_hora"]
