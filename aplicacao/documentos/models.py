from django.conf import settings
from django.db import models

from aplicacao.documentos.escolhas import (
    EtapaProcessamento,
    MetodoClassificacao,
    MetodoExtracao,
    OrigemDocumento,
    QualidadeExtracao,
    StatusProcessamento,
    TipoDadoExtraido,
    TipoDocumento,
)


class DocumentoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(excluido_em__isnull=True)


class Documento(models.Model):
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="documentos",
    )
    prestacao_parcial = models.ForeignKey(
        "prestacoes_contas.PrestacaoParcial",
        verbose_name="prestação parcial",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos",
    )
    nome_original = models.CharField("nome original", max_length=255)
    nome_armazenado = models.CharField("nome armazenado", max_length=255)
    tipo_documento = models.CharField(
        "tipo",
        max_length=40,
        choices=TipoDocumento.choices,
        default=TipoDocumento.NAO_CLASSIFICADO,
    )
    subtipo_documento = models.CharField("subtipo", max_length=120, blank=True)
    classificacao_original = models.CharField(
        "classificação original",
        max_length=40,
        choices=TipoDocumento.choices,
        blank=True,
    )
    tipo_sugerido = models.CharField(
        "tipo sugerido",
        max_length=40,
        choices=TipoDocumento.choices,
        blank=True,
    )
    mime_type = models.CharField("tipo MIME", max_length=120, blank=True)
    extensao = models.CharField("extensão", max_length=10, blank=True)
    tamanho_bytes = models.PositiveBigIntegerField("tamanho em bytes", default=0)
    hash_sha256 = models.CharField("SHA-256", max_length=64, blank=True, db_index=True)
    quantidade_paginas = models.PositiveIntegerField("quantidade de páginas", null=True, blank=True)
    origem = models.CharField(
        "origem",
        max_length=20,
        choices=OrigemDocumento.choices,
        default=OrigemDocumento.UPLOAD,
    )
    data_documento = models.DateField("data do documento", null=True, blank=True)
    status_processamento = models.CharField(
        "status",
        max_length=30,
        choices=StatusProcessamento.choices,
        default=StatusProcessamento.RECEBIDO,
        db_index=True,
    )
    etapa = models.CharField(
        "etapa",
        max_length=30,
        choices=EtapaProcessamento.choices,
        default=EtapaProcessamento.RECEBIDO,
    )
    metodo_classificacao = models.CharField(
        "método de classificação",
        max_length=30,
        choices=MetodoClassificacao.choices,
        default=MetodoClassificacao.NENHUM,
    )
    confianca_classificacao = models.DecimalField(
        "confiança da classificação",
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
    )
    fundamento_classificacao = models.TextField("fundamento da classificação", blank=True)
    classificacao_validada = models.BooleanField("classificação validada", default=False)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_validados",
    )
    validado_em = models.DateTimeField("validado em", null=True, blank=True)
    erro_processamento = models.TextField("erro de processamento", blank=True)
    demonstracao = models.BooleanField("dado de demonstração", default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_enviados",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    excluido_em = models.DateTimeField("excluído em", null=True, blank=True)

    objects = DocumentoQuerySet.as_manager()

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.nome_original

    @property
    def metodo_predominante(self) -> str:
        metodos = set(self.paginas.values_list("metodo_extracao", flat=True))
        if not metodos:
            return ""
        if metodos == {MetodoExtracao.NATIVO}:
            return MetodoExtracao.NATIVO
        if MetodoExtracao.HIBRIDO in metodos or (
            MetodoExtracao.NATIVO in metodos and MetodoExtracao.OCR in metodos
        ):
            return MetodoExtracao.HIBRIDO
        if MetodoExtracao.OCR in metodos:
            return MetodoExtracao.OCR
        return MetodoExtracao.SEM_TEXTO

    def get_metodo_predominante_display(self) -> str:
        rotulos = dict(MetodoExtracao.choices)
        return rotulos.get(self.metodo_predominante, "Não informado")


class PaginaDocumento(models.Model):
    documento = models.ForeignKey(Documento, verbose_name="documento", on_delete=models.CASCADE, related_name="paginas")
    numero_pagina = models.PositiveIntegerField("número da página")
    texto_extraido = models.TextField("texto extraído", blank=True)
    metodo_extracao = models.CharField("método de extração", max_length=20, choices=MetodoExtracao.choices)
    qualidade_extracao = models.CharField("qualidade da extração", max_length=20, choices=QualidadeExtracao.choices)
    necessitou_ocr = models.BooleanField("necessitou OCR", default=False)
    ocr_executado = models.BooleanField("OCR executado", default=False)
    quantidade_caracteres = models.PositiveIntegerField("quantidade de caracteres", default=0)
    dados_posicionais = models.JSONField("dados posicionais", default=dict, blank=True)
    erro_ocr = models.CharField("erro de OCR", max_length=300, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "página do documento"
        verbose_name_plural = "páginas do documento"
        ordering = ["numero_pagina"]
        constraints = [
            models.UniqueConstraint(fields=["documento", "numero_pagina"], name="pagina_unica_no_documento"),
            models.CheckConstraint(condition=models.Q(numero_pagina__gte=1), name="pagina_numero_positivo"),
        ]

    def __str__(self) -> str:
        return f"{self.documento_id} · página {self.numero_pagina}"


class DadoExtraidoDocumento(models.Model):
    """Candidato extraído. Não é um fato validado."""

    documento = models.ForeignKey(Documento, verbose_name="documento", on_delete=models.CASCADE, related_name="dados_extraidos")
    pagina = models.ForeignKey(
        PaginaDocumento,
        verbose_name="página",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dados_extraidos",
    )
    tipo = models.CharField("tipo", max_length=30, choices=TipoDadoExtraido.choices)
    valor = models.CharField("valor", max_length=255)
    trecho = models.TextField("trecho de origem", blank=True)
    metodo = models.CharField("método de extração", max_length=40)
    confianca = models.DecimalField("confiança", max_digits=4, decimal_places=3, null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "dado extraído do documento"
        verbose_name_plural = "dados extraídos do documento"
        ordering = ["tipo", "id"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()}: {self.valor}"


class ReprocessamentoDocumento(models.Model):
    documento = models.ForeignKey(Documento, verbose_name="documento", on_delete=models.CASCADE, related_name="reprocessamentos")
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="solicitado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reprocessamentos_solicitados",
    )
    solicitado_em = models.DateTimeField("solicitado em", auto_now_add=True)
    motivo = models.CharField("motivo", max_length=255, blank=True)
    resultado = models.CharField("resultado", max_length=20, blank=True)
    detalhe = models.CharField("detalhe", max_length=255, blank=True)

    class Meta:
        verbose_name = "reprocessamento"
        verbose_name_plural = "reprocessamentos"
        ordering = ["-solicitado_em"]
