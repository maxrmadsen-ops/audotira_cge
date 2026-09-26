import uuid

from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from aplicacao.normas.escolhas import (
    Esfera,
    MetodoRecuperacao,
    MetodoSegmentacao,
    SituacaoNorma,
    StatusProcessamentoNorma,
    TipoNorma,
    TipoRelacionamentoNorma,
)


class Norma(models.Model):
    """Fonte jurídica ou administrativa. Não é documento da prestação nem regra de análise."""

    grupo_id = models.UUIDField("grupo lógico", default=uuid.uuid4, db_index=True)
    versao = models.PositiveIntegerField("versão", default=1)
    norma_anterior = models.ForeignKey(
        "self",
        verbose_name="versão anterior",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="versoes_seguintes",
    )
    tipo_norma = models.CharField("tipo", max_length=40, choices=TipoNorma.choices)
    numero = models.CharField("número", max_length=40)
    ano = models.PositiveIntegerField("ano")
    titulo = models.CharField("título", max_length=300)
    ementa = models.TextField("ementa", blank=True)
    orgao_emissor = models.CharField("órgão emissor", max_length=200, blank=True)
    esfera = models.CharField("esfera", max_length=20, choices=Esfera.choices, blank=True)
    data_publicacao = models.DateField("data de publicação", null=True, blank=True)
    inicio_vigencia = models.DateField("início da vigência", null=True, blank=True)
    fim_vigencia = models.DateField("fim da vigência", null=True, blank=True)
    situacao = models.CharField(
        "situação",
        max_length=20,
        choices=SituacaoNorma.choices,
        default=SituacaoNorma.VIGENTE,
    )
    fonte = models.CharField("fonte", max_length=300, blank=True)
    arquivo = models.CharField("arquivo", max_length=255, blank=True)
    nome_original = models.CharField("nome original", max_length=255, blank=True)
    hash_sha256 = models.CharField("hash SHA-256", max_length=64, blank=True, db_index=True)
    observacoes = models.TextField("observações", blank=True)
    status_processamento = models.CharField(
        "status do processamento",
        max_length=20,
        choices=StatusProcessamentoNorma.choices,
        default=StatusProcessamentoNorma.RECEBIDA,
        db_index=True,
    )
    erro_processamento = models.TextField("erro de processamento", blank=True)
    desativada_em = models.DateTimeField("desativada em", null=True, blank=True, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="normas_criadas",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "norma"
        verbose_name_plural = "normas"
        ordering = ["-ano", "numero", "-versao"]
        constraints = [
            models.UniqueConstraint(fields=["grupo_id", "versao"], name="norma_grupo_versao_unica"),
            models.CheckConstraint(
                condition=models.Q(fim_vigencia__isnull=True)
                | models.Q(inicio_vigencia__isnull=True)
                | models.Q(fim_vigencia__gte=models.F("inicio_vigencia")),
                name="norma_vigencia_coerente",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_norma_display()} {self.numero}/{self.ano} v{self.versao}"

    @property
    def ativa(self) -> bool:
        return self.desativada_em is None


class RelacionamentoNorma(models.Model):
    """Ligação informada por uma pessoa. Esta onda não interpreta o efeito jurídico."""

    origem = models.ForeignKey(Norma, verbose_name="origem", on_delete=models.CASCADE, related_name="relacionamentos_origem")
    destino = models.ForeignKey(Norma, verbose_name="destino", on_delete=models.CASCADE, related_name="relacionamentos_destino")
    tipo = models.CharField("tipo", max_length=20, choices=TipoRelacionamentoNorma.choices)
    observacao = models.TextField("observação", blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "relacionamento entre normas"
        verbose_name_plural = "relacionamentos entre normas"
        constraints = [
            models.UniqueConstraint(fields=["origem", "destino", "tipo"], name="relacionamento_norma_unico"),
            models.CheckConstraint(condition=~models.Q(origem=models.F("destino")), name="relacionamento_norma_distinto"),
        ]

    def __str__(self) -> str:
        return f"{self.origem} {self.get_tipo_display()} {self.destino}"


class AplicabilidadeNorma(models.Model):
    """Contexto em que a norma pode ser usada. Campo vazio não restringe aquele eixo."""

    norma = models.ForeignKey(Norma, verbose_name="norma", on_delete=models.CASCADE, related_name="aplicabilidades")
    tipo_instrumento = models.CharField("tipo de instrumento", max_length=80, blank=True)
    orgao = models.CharField("órgão", max_length=200, blank=True)
    tipo_prestacao = models.CharField("tipo de prestação", max_length=80, blank=True)
    periodo_inicio = models.DateField("período inicial", null=True, blank=True)
    periodo_fim = models.DateField("período final", null=True, blank=True)
    categoria = models.CharField("categoria", max_length=80, blank=True)
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "aplicabilidade da norma"
        verbose_name_plural = "aplicabilidades da norma"

    def __str__(self) -> str:
        return f"Aplicabilidade de {self.norma}"


class TrechoNormativo(models.Model):
    norma = models.ForeignKey(Norma, verbose_name="norma", on_delete=models.CASCADE, related_name="trechos")
    ordem = models.PositiveIntegerField("ordem")
    pagina_inicio = models.PositiveIntegerField("página inicial", null=True, blank=True)
    pagina_fim = models.PositiveIntegerField("página final", null=True, blank=True)
    artigo = models.CharField("artigo", max_length=20, blank=True)
    paragrafo = models.CharField("parágrafo", max_length=20, blank=True)
    inciso = models.CharField("inciso", max_length=20, blank=True)
    alinea = models.CharField("alínea", max_length=8, blank=True)
    secao = models.CharField("seção", max_length=40, blank=True)
    titulo_secao = models.CharField("título da seção", max_length=300, blank=True)
    texto = models.TextField("texto")
    texto_normalizado = models.TextField("texto normalizado", blank=True)
    metadados = models.JSONField("metadados", default=dict, blank=True)
    embedding = VectorField("embedding", dimensions=settings.EMBEDDING_DIMENSAO, null=True, blank=True)
    hash_conteudo = models.CharField("hash do conteúdo", max_length=64, db_index=True)
    metodo_segmentacao = models.CharField(
        "método de segmentação",
        max_length=30,
        choices=MetodoSegmentacao.choices,
        default=MetodoSegmentacao.JANELA_TEXTUAL,
    )
    provedor_embedding = models.CharField("provedor do embedding", max_length=40, blank=True)
    modelo_embedding = models.CharField("modelo do embedding", max_length=80, blank=True)
    dimensao_embedding = models.PositiveIntegerField("dimensão do embedding", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "trecho normativo"
        verbose_name_plural = "trechos normativos"
        ordering = ["norma", "ordem"]
        constraints = [
            models.UniqueConstraint(fields=["norma", "ordem"], name="trecho_norma_ordem_unica"),
        ]
        indexes = [
            HnswIndex(
                name="trecho_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

    def __str__(self) -> str:
        dispositivo = self.artigo or "trecho"
        return f"{self.norma} · {dispositivo}"


class ConsultaNormativa(models.Model):
    texto = models.TextField("consulta")
    data_referencia = models.DateField("data de referência")
    tipo_instrumento = models.CharField("tipo de instrumento", max_length=80, blank=True)
    orgao = models.CharField("órgão", max_length=200, blank=True)
    tipo_prestacao = models.CharField("tipo de prestação", max_length=80, blank=True)
    categoria = models.CharField("categoria", max_length=80, blank=True)
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consultas_normativas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consultas_normativas",
    )
    filtros = models.JSONField("filtros", default=dict, blank=True)
    normas_consideradas = models.JSONField("normas consideradas", default=list, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "consulta normativa"
        verbose_name_plural = "consultas normativas"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Consulta em {self.criado_em:%d/%m/%Y %H:%M}"


class ResultadoConsultaNormativa(models.Model):
    consulta = models.ForeignKey(
        ConsultaNormativa,
        verbose_name="consulta",
        on_delete=models.CASCADE,
        related_name="resultados",
    )
    trecho = models.ForeignKey(TrechoNormativo, verbose_name="trecho", on_delete=models.PROTECT, related_name="resultados")
    ordem = models.PositiveIntegerField("ordem")
    score_lexical = models.FloatField("score lexical", null=True, blank=True)
    score_vetorial = models.FloatField("score vetorial", null=True, blank=True)
    score_final = models.FloatField("score final")
    metodo = models.CharField("método", max_length=20, choices=MetodoRecuperacao.choices)

    class Meta:
        verbose_name = "resultado de consulta normativa"
        verbose_name_plural = "resultados de consulta normativa"
        ordering = ["consulta", "ordem"]

    def __str__(self) -> str:
        return f"Resultado {self.ordem} da consulta {self.consulta_id}"


class ReprocessamentoNorma(models.Model):
    norma = models.ForeignKey(Norma, verbose_name="norma", on_delete=models.CASCADE, related_name="reprocessamentos")
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="solicitado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    solicitado_em = models.DateTimeField("solicitado em", auto_now_add=True)
    motivo = models.CharField("motivo", max_length=200, blank=True)
    resultado = models.CharField("resultado", max_length=40, blank=True)

    class Meta:
        verbose_name = "reprocessamento de norma"
        verbose_name_plural = "reprocessamentos de norma"
        ordering = ["-solicitado_em"]
