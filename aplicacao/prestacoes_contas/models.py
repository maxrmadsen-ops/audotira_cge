from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from aplicacao.entidades.models import Rastreavel
from aplicacao.prestacoes_contas.campos import DinheiroField
from aplicacao.prestacoes_contas.escolhas import (
    FasePrestacao,
    MeioPagamento,
    NaturezaItem,
    SituacaoPrestacao,
    TipoDocumentoFiscal,
    TipoInstrumento,
    TipoMovimentacao,
    TipoPrestacaoParcial,
)

ZERO = Decimal("0.00")


def _soma(queryset, campo: str) -> Decimal | None:
    total = queryset.aggregate(total=Sum(campo))["total"]
    if total is None:
        return None
    return total


class PrestacaoContas(Rastreavel):
    """Processo de prestação de contas. Não representa um único termo fixo."""

    numero_processo = models.CharField("número do processo", max_length=60, unique=True)
    concedente = models.ForeignKey(
        "entidades.Entidade",
        verbose_name="concedente",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prestacoes_como_concedente",
    )
    beneficiario = models.ForeignKey(
        "entidades.Entidade",
        verbose_name="beneficiário",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prestacoes_como_beneficiario",
    )
    objeto = models.TextField("objeto", blank=True)
    valor_total = DinheiroField("valor total", null=True, blank=True)
    data_inicio = models.DateField("data de início", null=True, blank=True)
    data_fim = models.DateField("data de fim", null=True, blank=True)
    situacao = models.CharField(
        "situação",
        max_length=20,
        choices=SituacaoPrestacao.choices,
        default=SituacaoPrestacao.EM_ELABORACAO,
    )
    fase = models.CharField(
        "fase",
        max_length=20,
        choices=FasePrestacao.choices,
        default=FasePrestacao.PACTUACAO,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prestacoes_criadas",
    )

    class Meta:
        verbose_name = "prestação de contas"
        verbose_name_plural = "prestações de contas"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor_total__isnull=True) | models.Q(valor_total__gte=0),
                name="prestacao_valor_total_nao_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(data_inicio__isnull=True)
                | models.Q(data_fim__isnull=True)
                | models.Q(data_fim__gte=models.F("data_inicio")),
                name="prestacao_datas_coerentes",
            ),
        ]

    def __str__(self) -> str:
        return self.numero_processo

    @property
    def instrumento_principal(self):
        return self.instrumentos.order_by("-principal", "id").first()

    @property
    def numero_instrumento(self) -> str:
        instrumento = self.instrumento_principal
        return instrumento.numero if instrumento else ""

    @property
    def tipo_instrumento(self) -> str:
        instrumento = self.instrumento_principal
        return instrumento.get_tipo_display() if instrumento else ""

    @property
    def valor_previsto(self) -> Decimal | None:
        total_itens = _soma(ItemPlanoTrabalho.objects.filter(plano__prestacao=self), "valor_previsto")
        if total_itens is not None:
            return total_itens
        instrumento = self.instrumento_principal
        if instrumento and instrumento.valor is not None:
            return instrumento.valor
        return self.valor_total

    @property
    def valor_executado(self) -> Decimal | None:
        return _soma(self.despesas.all(), "valor")

    @property
    def diferenca_previsto_executado(self) -> Decimal | None:
        if self.valor_previsto is None or self.valor_executado is None:
            return None
        return self.valor_previsto - self.valor_executado


class Instrumento(Rastreavel):
    """Instrumento que formaliza a transferência. A prestação pode ter mais de um."""

    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="instrumentos",
    )
    numero = models.CharField("número", max_length=60, blank=True)
    tipo = models.CharField("tipo", max_length=30, choices=TipoInstrumento.choices, default=TipoInstrumento.OUTRO)
    data_assinatura = models.DateField("data de assinatura", null=True, blank=True)
    vigencia_inicio = models.DateField("início da vigência", null=True, blank=True)
    vigencia_fim = models.DateField("fim da vigência", null=True, blank=True)
    valor = DinheiroField("valor", null=True, blank=True)
    objeto = models.TextField("objeto", blank=True)
    principal = models.BooleanField("principal", default=True)

    class Meta:
        verbose_name = "instrumento"
        verbose_name_plural = "instrumentos"
        ordering = ["-principal", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="instrumento_valor_nao_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(vigencia_inicio__isnull=True)
                | models.Q(vigencia_fim__isnull=True)
                | models.Q(vigencia_fim__gte=models.F("vigencia_inicio")),
                name="instrumento_vigencia_coerente",
            ),
        ]

    def __str__(self) -> str:
        return self.numero or f"Instrumento {self.pk or ''}".strip()


class PlanoTrabalho(Rastreavel):
    """O que foi pactuado. Itens e metas detalham o previsto."""

    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="planos",
    )
    instrumento = models.ForeignKey(
        Instrumento,
        verbose_name="instrumento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="planos",
    )
    titulo = models.CharField("título", max_length=255)
    versao = models.PositiveIntegerField("versão", default=1)
    vigencia_inicio = models.DateField("início da vigência", null=True, blank=True)
    vigencia_fim = models.DateField("fim da vigência", null=True, blank=True)

    class Meta:
        verbose_name = "plano de trabalho"
        verbose_name_plural = "planos de trabalho"
        ordering = ["versao", "id"]
        constraints = [
            models.UniqueConstraint(fields=["prestacao", "versao"], name="plano_versao_unica_na_prestacao"),
            models.CheckConstraint(
                condition=models.Q(vigencia_inicio__isnull=True)
                | models.Q(vigencia_fim__isnull=True)
                | models.Q(vigencia_fim__gte=models.F("vigencia_inicio")),
                name="plano_vigencia_coerente",
            ),
        ]

    def __str__(self) -> str:
        return self.titulo

    @property
    def valor_previsto(self) -> Decimal | None:
        return _soma(self.itens.all(), "valor_previsto")


class ItemPlanoTrabalho(Rastreavel):
    plano = models.ForeignKey(PlanoTrabalho, verbose_name="plano de trabalho", on_delete=models.CASCADE, related_name="itens")
    categoria = models.CharField("categoria", max_length=120, blank=True)
    descricao = models.TextField("descrição")
    quantidade = models.DecimalField("quantidade", max_digits=12, decimal_places=3, null=True, blank=True)
    unidade = models.CharField("unidade", max_length=40, blank=True)
    valor_previsto = DinheiroField("valor previsto", null=True, blank=True)
    periodo_inicio = models.DateField("início do período", null=True, blank=True)
    periodo_fim = models.DateField("fim do período", null=True, blank=True)
    natureza = models.CharField("natureza", max_length=20, choices=NaturezaItem.choices, default=NaturezaItem.OUTRO)
    ordem = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "item do plano de trabalho"
        verbose_name_plural = "itens do plano de trabalho"
        ordering = ["ordem", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor_previsto__isnull=True) | models.Q(valor_previsto__gte=0),
                name="item_plano_valor_nao_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade__isnull=True) | models.Q(quantidade__gte=0),
                name="item_plano_quantidade_nao_negativa",
            ),
        ]

    def __str__(self) -> str:
        return self.descricao[:80]

    @property
    def valor_realizado(self) -> Decimal | None:
        return _soma(self.despesas.all(), "valor")


class Meta(Rastreavel):
    plano = models.ForeignKey(PlanoTrabalho, verbose_name="plano de trabalho", on_delete=models.CASCADE, related_name="metas")
    codigo = models.CharField("código", max_length=40, blank=True)
    descricao = models.TextField("descrição")
    indicador = models.CharField("indicador", max_length=255, blank=True)
    quantidade_prevista = models.DecimalField(
        "quantidade prevista",
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    unidade = models.CharField("unidade", max_length=40, blank=True)
    periodo_inicio = models.DateField("início do período", null=True, blank=True)
    periodo_fim = models.DateField("fim do período", null=True, blank=True)

    class Meta:
        verbose_name = "meta"
        verbose_name_plural = "metas"
        ordering = ["codigo", "id"]

    def __str__(self) -> str:
        return self.descricao[:80]


class PrestacaoParcial(Rastreavel):
    """Parcela ou prestação final. A quantidade não é fixa."""

    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="parciais",
    )
    tipo = models.CharField("tipo", max_length=20, choices=TipoPrestacaoParcial.choices, default=TipoPrestacaoParcial.PARCIAL)
    numero_ordem = models.PositiveIntegerField("ordem")
    periodo_inicio = models.DateField("início do período", null=True, blank=True)
    periodo_fim = models.DateField("fim do período", null=True, blank=True)
    descricao = models.CharField("descrição", max_length=255, blank=True)

    class Meta:
        verbose_name = "prestação parcial"
        verbose_name_plural = "prestações parciais"
        ordering = ["numero_ordem", "id"]
        constraints = [
            models.UniqueConstraint(fields=["prestacao", "numero_ordem"], name="parcial_ordem_unica_na_prestacao"),
            models.CheckConstraint(
                condition=models.Q(periodo_inicio__isnull=True)
                | models.Q(periodo_fim__isnull=True)
                | models.Q(periodo_fim__gte=models.F("periodo_inicio")),
                name="parcial_periodo_coerente",
            ),
        ]

    def __str__(self) -> str:
        rotulo = "Prestação final" if self.tipo == TipoPrestacaoParcial.FINAL else f"Prestação parcial {self.numero_ordem:02d}"
        return rotulo


class Despesa(Rastreavel):
    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="despesas",
    )
    prestacao_parcial = models.ForeignKey(
        PrestacaoParcial,
        verbose_name="prestação parcial",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="despesas",
    )
    item_plano = models.ForeignKey(
        ItemPlanoTrabalho,
        verbose_name="item do plano",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="despesas",
    )
    fornecedor = models.ForeignKey(
        "entidades.Fornecedor",
        verbose_name="fornecedor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="despesas",
    )
    descricao = models.TextField("descrição", blank=True)
    valor = DinheiroField("valor", null=True, blank=True)
    data = models.DateField("data", null=True, blank=True)
    categoria = models.CharField("categoria", max_length=120, blank=True)
    natureza = models.CharField("natureza", max_length=20, choices=NaturezaItem.choices, blank=True)

    class Meta:
        verbose_name = "despesa"
        verbose_name_plural = "despesas"
        ordering = ["data", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="despesa_valor_nao_negativo",
            ),
        ]

    def __str__(self) -> str:
        return self.descricao[:80] or f"Despesa {self.pk or ''}".strip()


class DocumentoFiscal(Rastreavel):
    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="documentos_fiscais",
    )
    despesas = models.ManyToManyField(Despesa, verbose_name="despesas", blank=True, related_name="documentos_fiscais")
    emitente = models.ForeignKey(
        "entidades.Fornecedor",
        verbose_name="emitente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_emitidos",
    )
    tipo = models.CharField("tipo", max_length=20, choices=TipoDocumentoFiscal.choices, default=TipoDocumentoFiscal.OUTRO)
    numero = models.CharField("número", max_length=40, blank=True)
    serie = models.CharField("série", max_length=20, blank=True)
    data_emissao = models.DateField("data de emissão", null=True, blank=True)
    valor = DinheiroField("valor", null=True, blank=True)

    class Meta:
        verbose_name = "documento fiscal"
        verbose_name_plural = "documentos fiscais"
        ordering = ["data_emissao", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="documento_fiscal_valor_nao_negativo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.numero}".strip()


class Pagamento(Rastreavel):
    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="pagamentos",
    )
    prestacao_parcial = models.ForeignKey(
        PrestacaoParcial,
        verbose_name="prestação parcial",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pagamentos",
    )
    despesas = models.ManyToManyField(Despesa, verbose_name="despesas", blank=True, related_name="pagamentos")
    documentos_fiscais = models.ManyToManyField(
        DocumentoFiscal,
        verbose_name="documentos fiscais",
        blank=True,
        related_name="pagamentos",
    )
    data = models.DateField("data", null=True, blank=True)
    valor = DinheiroField("valor", null=True, blank=True)
    meio = models.CharField("meio", max_length=20, choices=MeioPagamento.choices, blank=True)
    identificador = models.CharField("identificador", max_length=80, blank=True)

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "pagamentos"
        ordering = ["data", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="pagamento_valor_nao_negativo",
            ),
        ]

    def __str__(self) -> str:
        return self.identificador or f"Pagamento {self.pk or ''}".strip()


class MovimentacaoBancaria(Rastreavel):
    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="movimentacoes",
    )
    pagamentos = models.ManyToManyField(Pagamento, verbose_name="pagamentos", blank=True, related_name="movimentacoes")
    data = models.DateField("data", null=True, blank=True)
    valor = DinheiroField("valor", null=True, blank=True)
    tipo = models.CharField("tipo", max_length=20, choices=TipoMovimentacao.choices, blank=True)
    historico = models.CharField("histórico", max_length=255, blank=True)
    identificador = models.CharField("identificador", max_length=80, blank=True)

    class Meta:
        verbose_name = "movimentação bancária"
        verbose_name_plural = "movimentações bancárias"
        ordering = ["data", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="movimentacao_valor_nao_negativo",
            ),
        ]

    def __str__(self) -> str:
        return self.historico or self.identificador or f"Movimentação {self.pk or ''}".strip()


class Contrapartida(Rastreavel):
    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="contrapartidas",
    )
    item_plano = models.ForeignKey(
        ItemPlanoTrabalho,
        verbose_name="item do plano",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contrapartidas",
    )
    descricao = models.TextField("descrição", blank=True)
    valor = DinheiroField("valor", null=True, blank=True)
    data = models.DateField("data", null=True, blank=True)

    class Meta:
        verbose_name = "contrapartida"
        verbose_name_plural = "contrapartidas"
        ordering = ["data", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="contrapartida_valor_nao_negativo",
            ),
        ]

    def __str__(self) -> str:
        return self.descricao[:80] or "Contrapartida"


class Devolucao(Rastreavel):
    prestacao = models.ForeignKey(
        PrestacaoContas,
        verbose_name="prestação de contas",
        on_delete=models.CASCADE,
        related_name="devolucoes",
    )
    prestacao_parcial = models.ForeignKey(
        PrestacaoParcial,
        verbose_name="prestação parcial",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="devolucoes",
    )
    data = models.DateField("data", null=True, blank=True)
    valor = DinheiroField("valor", null=True, blank=True)
    motivo = models.TextField("motivo", blank=True)

    class Meta:
        verbose_name = "devolução"
        verbose_name_plural = "devoluções"
        ordering = ["data", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__isnull=True) | models.Q(valor__gte=0),
                name="devolucao_valor_nao_negativo",
            ),
        ]

    def __str__(self) -> str:
        return self.motivo[:80] or "Devolução"
