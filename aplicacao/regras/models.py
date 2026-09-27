from django.conf import settings
from django.db import models

from aplicacao.regras.escolhas import (
    CapacidadeExecucao,
    Encaminhamento,
    EtapaAnalise,
    ModoExecucao,
    SINTESE_NAO_CONCLUSIVA,
    StatusAnalise,
    StatusTecnico,
    TipoDependencia,
    TipoExecucaoTecnica,
)


class RegraAnalise(models.Model):
    """Regra versionada. O texto original da matriz não é reescrito pela classificação técnica."""

    codigo = models.CharField("código", max_length=20, db_index=True)
    versao = models.PositiveIntegerField("versão", default=1)
    categoria = models.CharField("categoria", max_length=80)
    titulo = models.CharField("título", max_length=400)
    descricao_original = models.TextField("descrição original")
    fonte_normativa_original = models.TextField("fonte normativa original", blank=True)
    aplicabilidade_original = models.TextField("aplicabilidade original", blank=True)
    entradas_necessarias = models.TextField("entradas necessárias", blank=True)
    dados_extrair = models.TextField("dados a extrair", blank=True)
    logica_verificacao = models.TextField("lógica de verificação", blank=True)
    resultados_possiveis = models.TextField("resultados possíveis", blank=True)
    evidencia_obrigatoria = models.TextField("evidência obrigatória", blank=True)
    limitacao_observacao = models.TextField("limitação ou observação", blank=True)
    tratamento_analista = models.TextField("tratamento para o analista", blank=True)
    tipo_execucao = models.CharField("tipo técnico", max_length=30, choices=TipoExecucaoTecnica.choices)
    capacidade = models.CharField("capacidade", max_length=30, choices=CapacidadeExecucao.choices)
    executor = models.CharField("executor", max_length=40)
    configuracao = models.JSONField("configuração", default=dict, blank=True)
    conteudo_original = models.JSONField("conteúdo original", default=dict, blank=True)
    ativa = models.BooleanField("ativa", default=True, db_index=True)
    ordem = models.PositiveIntegerField("ordem", default=0)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "regra de análise"
        verbose_name_plural = "regras de análise"
        ordering = ["ordem", "codigo"]
        constraints = [
            models.UniqueConstraint(fields=["codigo", "versao"], name="regra_codigo_versao_unica"),
            models.UniqueConstraint(fields=["codigo"], condition=models.Q(ativa=True), name="regra_ativa_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} v{self.versao}"

    def tokens_resultado(self) -> list[str]:
        return [parte.strip() for parte in self.resultados_possiveis.split("/") if parte.strip()]


class RegraDependencia(models.Model):
    regra = models.ForeignKey(RegraAnalise, verbose_name="regra", on_delete=models.CASCADE, related_name="dependencias")
    codigo_requisito = models.CharField("código do requisito", max_length=20)
    tipo = models.CharField("tipo", max_length=30, choices=TipoDependencia.choices)
    parametro = models.JSONField("parâmetro", default=dict, blank=True)

    class Meta:
        verbose_name = "dependência de regra"
        verbose_name_plural = "dependências de regra"
        constraints = [
            models.UniqueConstraint(fields=["regra", "codigo_requisito", "tipo"], name="dependencia_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.regra.codigo} {self.tipo} {self.codigo_requisito}"


class ExecucaoAnalise(models.Model):
    """Uma rodada do motor. A síntese nunca é a conclusão administrativa da prestação."""

    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="execucoes_analise",
    )
    versao_catalogo = models.CharField("versão do catálogo", max_length=64)
    modo_execucao = models.CharField("modo", max_length=20, choices=ModoExecucao.choices, default=ModoExecucao.NORMAL)
    modo_teste_cego = models.BooleanField("teste cego", default=False)
    iniciada_em = models.DateTimeField("iniciada em", null=True, blank=True)
    finalizada_em = models.DateTimeField("finalizada em", null=True, blank=True)
    status = models.CharField("status", max_length=30, choices=StatusAnalise.choices, default=StatusAnalise.EM_ANDAMENTO)
    etapa = models.CharField("etapa", max_length=40, choices=EtapaAnalise.choices, default=EtapaAnalise.PREPARANDO_CONTEXTO)
    sintese = models.CharField("síntese", max_length=40, default=SINTESE_NAO_CONCLUSIVA)
    total_regras = models.PositiveIntegerField("total de regras", default=0)
    executadas = models.PositiveIntegerField("executadas", default=0)
    nao_aplicaveis = models.PositiveIntegerField("não aplicáveis", default=0)
    nao_verificaveis = models.PositiveIntegerField("não verificáveis", default=0)
    requer_ia = models.PositiveIntegerField("requerem IA", default=0)
    requer_analista = models.PositiveIntegerField("requerem analista", default=0)
    erros = models.PositiveIntegerField("erros", default=0)
    documentos_excluidos = models.JSONField("documentos excluídos", default=list, blank=True)
    erro = models.TextField("erro", blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analises_executadas",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "execução de análise"
        verbose_name_plural = "execuções de análise"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Análise {self.pk} · {self.prestacao_contas}"


class ExecucaoRegra(models.Model):
    """Execução presa à versão da regra. Uma versão nova não reescreve este registro."""

    analise = models.ForeignKey(ExecucaoAnalise, verbose_name="análise", on_delete=models.CASCADE, related_name="execucoes")
    regra = models.ForeignKey(RegraAnalise, verbose_name="regra", on_delete=models.PROTECT, related_name="execucoes")
    snapshot = models.JSONField("instantâneo da regra", default=dict)
    resultado_funcional = models.CharField("resultado funcional", max_length=120, blank=True)
    status_tecnico = models.CharField("status técnico", max_length=30, choices=StatusTecnico.choices)
    encaminhamento = models.CharField(
        "encaminhamento",
        max_length=30,
        choices=Encaminhamento.choices,
        default=Encaminhamento.NENHUM,
    )
    limitacao = models.TextField("limitação", blank=True)
    entradas = models.JSONField("entradas", default=dict, blank=True)
    ordem = models.PositiveIntegerField("ordem", default=0)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "execução de regra"
        verbose_name_plural = "execuções de regra"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.regra.codigo} · {self.resultado_funcional}"


class ReferenciaExecucao(models.Model):
    """Ponteiro para a fonte usada. Não copia o documento inteiro."""

    execucao = models.ForeignKey(ExecucaoRegra, verbose_name="execução", on_delete=models.CASCADE, related_name="referencias")
    tipo_fonte = models.CharField("tipo da fonte", max_length=40)
    identificador = models.CharField("identificador", max_length=80, blank=True)
    documento = models.ForeignKey(
        "documentos.Documento",
        verbose_name="documento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referencias_regra",
    )
    pagina = models.ForeignKey(
        "documentos.PaginaDocumento",
        verbose_name="página",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referencias_regra",
    )
    trecho_normativo = models.ForeignKey(
        "normas.TrechoNormativo",
        verbose_name="trecho normativo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referencias_regra",
    )
    trecho = models.CharField("trecho", max_length=500, blank=True)
    campo = models.CharField("campo", max_length=80, blank=True)
    valor_utilizado = models.CharField("valor utilizado", max_length=255, blank=True)
    papel_na_regra = models.CharField("papel na regra", max_length=80, blank=True)

    class Meta:
        verbose_name = "referência da execução"
        verbose_name_plural = "referências da execução"

    def __str__(self) -> str:
        return f"{self.tipo_fonte} {self.identificador}".strip()


class CalculoExecucaoRegra(models.Model):
    execucao = models.ForeignKey(ExecucaoRegra, verbose_name="execução", on_delete=models.CASCADE, related_name="calculos")
    operacao = models.CharField("operação", max_length=80)
    operandos = models.JSONField("operandos", default=dict)
    resultado = models.DecimalField("resultado", max_digits=16, decimal_places=4)
    unidade = models.CharField("unidade", max_length=20, blank=True)

    class Meta:
        verbose_name = "cálculo da execução"
        verbose_name_plural = "cálculos da execução"

    def __str__(self) -> str:
        return f"{self.operacao} = {self.resultado}"
