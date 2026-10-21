from django.conf import settings
from django.db import models

from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao
from aplicacao.laboratorio.catalogo import escolhas_tipo
from aplicacao.laboratorio.escolhas import (
    ConferenciaInstrumento,
    EstadoCampo,
    EstadoClassificacao,
    EstadoRevisao,
    EstadoVinculo,
    PrioridadePendencia,
    StatusPendencia,
)


class LoteLaboratorio(models.Model):
    """Importação imutável de um PDF de prestação parcial para o laboratório."""

    prestacao_parceria = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="processo da parceria",
        on_delete=models.PROTECT,
        related_name="lotes_laboratorio",
    )
    documento = models.OneToOneField(
        "documentos.Documento",
        verbose_name="documento original",
        on_delete=models.PROTECT,
        related_name="lote_laboratorio",
    )
    numero_processo_parcial = models.CharField("processo da prestação parcial", max_length=60)
    numero_instrumento = models.CharField("instrumento correspondente", max_length=80, blank=True)
    estado_conferencia_instrumento = models.CharField(
        "estado da conferência do instrumento",
        max_length=20,
        choices=ConferenciaInstrumento.choices,
        default=ConferenciaInstrumento.PENDENTE,
    )
    origem = models.CharField("origem do arquivo", max_length=255, blank=True)
    hash_sha256 = models.CharField("SHA-256 do original", max_length=64, db_index=True)
    tamanho_bytes = models.PositiveBigIntegerField("tamanho em bytes", default=0)
    quantidade_paginas = models.PositiveIntegerField("quantidade de páginas", default=0)
    tecnica_predominante = models.CharField("técnica predominante", max_length=40, blank=True)
    limitacoes = models.TextField("limitações registradas", blank=True)
    importado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="importado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lotes_laboratorio_importados",
    )
    importado_em = models.DateTimeField("importado em", auto_now_add=True)
    processado_em = models.DateTimeField("processado em", null=True, blank=True)
    duracao_processamento_ms = models.PositiveIntegerField("duração do processamento (ms)", null=True, blank=True)

    class Meta:
        verbose_name = "lote do laboratório"
        verbose_name_plural = "lotes do laboratório"
        ordering = ["-importado_em"]

    def __str__(self) -> str:
        return f"{self.numero_processo_parcial} · {self.hash_sha256[:12]}"


class InventarioPagina(models.Model):
    lote = models.ForeignKey(LoteLaboratorio, verbose_name="lote", on_delete=models.CASCADE, related_name="paginas")
    pagina_documento = models.ForeignKey(
        "documentos.PaginaDocumento",
        verbose_name="página do documento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventarios_laboratorio",
    )
    numero_fisico = models.PositiveIntegerField("número físico no PDF")
    numero_impresso = models.CharField("número impresso", max_length=40, blank=True)
    tipos_candidatos = models.JSONField("tipos documentais candidatos", default=list, blank=True)
    quantidade_regioes = models.PositiveIntegerField("quantidade de regiões", default=0)
    tem_texto_digital = models.BooleanField("possui texto digital", default=False)
    tem_imagem = models.BooleanField("possui conteúdo de imagem", default=True)
    qualidade_extracao = models.CharField(
        "qualidade da extração",
        max_length=20,
        choices=QualidadeExtracao.choices,
        default=QualidadeExtracao.AUSENTE,
    )
    legibilidade = models.CharField("indicador de legibilidade", max_length=40, blank=True)
    tecnica_utilizada = models.CharField(
        "técnica utilizada",
        max_length=20,
        choices=MetodoExtracao.choices,
        blank=True,
    )
    tecnica_recomendada = models.CharField("técnica recomendada", max_length=40, blank=True)
    estado_classificacao = models.CharField(
        "estado da classificação",
        max_length=20,
        choices=EstadoClassificacao.choices,
        default=EstadoClassificacao.INCONCLUSIVO,
    )
    estado_revisao = models.CharField(
        "estado da revisão humana",
        max_length=20,
        choices=EstadoRevisao.choices,
        default=EstadoRevisao.PENDENTE,
    )
    quantidade_caracteres = models.PositiveIntegerField("quantidade de caracteres", default=0)
    trecho_amostra = models.CharField("trecho de amostra", max_length=280, blank=True)
    proveniencia = models.CharField("evidência de proveniência", max_length=255, blank=True)

    class Meta:
        verbose_name = "página inventariada"
        verbose_name_plural = "páginas inventariadas"
        ordering = ["numero_fisico"]
        constraints = [
            models.UniqueConstraint(fields=["lote", "numero_fisico"], name="lab_pagina_unica_no_lote"),
        ]

    def __str__(self) -> str:
        return f"Página física {self.numero_fisico}"


class RegiaoDocumental(models.Model):
    lote = models.ForeignKey(LoteLaboratorio, verbose_name="lote", on_delete=models.CASCADE, related_name="regioes")
    pagina = models.ForeignKey(InventarioPagina, verbose_name="página", on_delete=models.CASCADE, related_name="regioes")
    tipo_documental = models.CharField("tipo documental", max_length=60, choices=escolhas_tipo())
    ordem = models.PositiveIntegerField("ordem na página", default=1)
    x = models.FloatField("x relativo", default=0.0)
    y = models.FloatField("y relativo", default=0.0)
    largura = models.FloatField("largura relativa", default=1.0)
    altura = models.FloatField("altura relativa", default=1.0)
    metodo_deteccao = models.CharField("método de detecção", max_length=60, blank=True)
    confianca = models.DecimalField("confiança", max_digits=4, decimal_places=3, null=True, blank=True)
    versao_classificacao = models.PositiveIntegerField("versão da classificação", default=1)
    estado_classificacao = models.CharField(
        "estado da classificação",
        max_length=20,
        choices=EstadoClassificacao.choices,
        default=EstadoClassificacao.PROPOSTO,
    )
    estado_revisao = models.CharField(
        "estado da revisão",
        max_length=20,
        choices=EstadoRevisao.choices,
        default=EstadoRevisao.PENDENTE,
    )
    justificativa = models.TextField("justificativa da revisão", blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="regioes_laboratorio_revisadas",
    )
    revisado_em = models.DateTimeField("revisado em", null=True, blank=True)
    grupo_peca = models.CharField("identificador da peça multipágina", max_length=80, blank=True)
    texto_regiao = models.TextField("texto da região", blank=True)
    versao_extracao = models.CharField("versão da extração", max_length=20, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "região documental"
        verbose_name_plural = "regiões documentais"
        ordering = ["pagina__numero_fisico", "ordem", "id"]

    def __str__(self) -> str:
        return f"{self.tipo_documental} · p.{self.pagina.numero_fisico}"


class CampoExtraido(models.Model):
    regiao = models.ForeignKey(RegiaoDocumental, verbose_name="região", on_delete=models.CASCADE, related_name="campos")
    esquema = models.CharField("esquema tipado", max_length=40)
    chave = models.CharField("chave do campo", max_length=80)
    rotulo = models.CharField("rótulo", max_length=120)
    valor_original = models.TextField("valor original", blank=True)
    valor_normalizado = models.TextField("valor normalizado", blank=True)
    numero_pagina = models.PositiveIntegerField("página física")
    trecho_evidencia = models.TextField("trecho de evidência", blank=True)
    evidencia_x = models.FloatField("x da evidência", null=True, blank=True)
    evidencia_y = models.FloatField("y da evidência", null=True, blank=True)
    evidencia_largura = models.FloatField("largura da evidência", null=True, blank=True)
    evidencia_altura = models.FloatField("altura da evidência", null=True, blank=True)
    localizacao_precisa = models.BooleanField("localização precisa", default=False)
    metodo = models.CharField("método", max_length=60, blank=True)
    estado_confianca = models.CharField("estado de confiança", max_length=40, blank=True)
    estado_revisao = models.CharField(
        "estado da revisão",
        max_length=20,
        choices=EstadoCampo.choices,
        default=EstadoCampo.PENDENTE,
    )
    obrigatorio = models.BooleanField("campo obrigatório no esquema", default=False)
    historico_correcoes = models.JSONField("histórico de correções", default=list, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campos_laboratorio_revisados",
    )
    revisado_em = models.DateTimeField("revisado em", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "campo extraído"
        verbose_name_plural = "campos extraídos"
        ordering = ["regiao_id", "chave", "id"]

    def __str__(self) -> str:
        return f"{self.chave}: {self.valor_original[:40]}"


class RubricaExtraida(models.Model):
    """Linha de provento ou desconto, com revisão própria."""

    class Natureza(models.TextChoices):
        PROVENTO = "provento", "Provento"
        DESCONTO = "desconto", "Desconto"

    regiao = models.ForeignKey(RegiaoDocumental, verbose_name="região", on_delete=models.CASCADE, related_name="rubricas")
    ordem = models.PositiveIntegerField("ordem", default=1)
    codigo = models.CharField("código", max_length=10, blank=True)
    descricao = models.CharField("descrição", max_length=180, blank=True)
    referencia = models.CharField("referência", max_length=40, blank=True)
    unidade = models.CharField("unidade da referência", max_length=20, blank=True)
    natureza = models.CharField("natureza", max_length=20, choices=Natureza.choices)
    valor_original = models.CharField("valor original", max_length=40, blank=True)
    valor_normalizado = models.CharField("valor normalizado", max_length=40, blank=True)
    trecho_evidencia = models.TextField("trecho de evidência", blank=True)
    evidencia_x = models.FloatField("x da evidência", null=True, blank=True)
    evidencia_y = models.FloatField("y da evidência", null=True, blank=True)
    evidencia_largura = models.FloatField("largura da evidência", null=True, blank=True)
    evidencia_altura = models.FloatField("altura da evidência", null=True, blank=True)
    localizacao_precisa = models.BooleanField("localização precisa", default=False)
    metodo = models.CharField("método", max_length=60, blank=True)
    estado_confianca = models.CharField("estado de confiança", max_length=40, blank=True)
    estado_revisao = models.CharField(
        "estado da revisão",
        max_length=20,
        choices=EstadoCampo.choices,
        default=EstadoCampo.PENDENTE,
    )
    historico_correcoes = models.JSONField("histórico de correções", default=list, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rubricas_laboratorio_revisadas",
    )
    revisado_em = models.DateTimeField("revisado em", null=True, blank=True)

    class Meta:
        verbose_name = "rubrica extraída"
        verbose_name_plural = "rubricas extraídas"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.descricao}"


class VinculoEvidencia(models.Model):
    lote = models.ForeignKey(LoteLaboratorio, verbose_name="lote", on_delete=models.CASCADE, related_name="vinculos")
    origem = models.ForeignKey(
        RegiaoDocumental,
        verbose_name="região de origem",
        on_delete=models.CASCADE,
        related_name="vinculos_origem",
    )
    destino = models.ForeignKey(
        RegiaoDocumental,
        verbose_name="região de destino",
        on_delete=models.CASCADE,
        related_name="vinculos_destino",
    )
    tipo_vinculo = models.CharField("tipo de vínculo", max_length=60)
    criterios = models.JSONField("critérios utilizados", default=list, blank=True)
    divergencias = models.JSONField("divergências observadas", default=list, blank=True)
    estado = models.CharField(
        "estado de confirmação",
        max_length=20,
        choices=EstadoVinculo.choices,
        default=EstadoVinculo.SUGERIDO,
    )
    justificativa = models.TextField("justificativa", blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vinculos_laboratorio_revisados",
    )
    revisado_em = models.DateTimeField("revisado em", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "vínculo entre evidências"
        verbose_name_plural = "vínculos entre evidências"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.tipo_vinculo} · {self.estado}"


class CadeiaConciliacao(models.Model):
    """Sugestão de cadeia previsto → executado → comprovado. Não decide a prestação."""

    lote = models.ForeignKey(LoteLaboratorio, verbose_name="lote", on_delete=models.CASCADE, related_name="cadeias")
    codigo = models.CharField("código estável", max_length=80)
    titulo = models.CharField("título", max_length=255)
    item_plano = models.ForeignKey(
        "prestacoes_contas.ItemPlanoTrabalho",
        verbose_name="item previsto sugerido",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cadeias_sugeridas",
    )
    criterio_item = models.TextField("critério do item previsto", blank=True)
    execucao = models.ForeignKey(
        RegiaoDocumental,
        verbose_name="documento de execução",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cadeias_execucao",
    )
    comprovante = models.ForeignKey(
        RegiaoDocumental,
        verbose_name="comprovante sugerido",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cadeias_comprovante",
    )
    apoio = models.ForeignKey(
        RegiaoDocumental,
        verbose_name="documento de apoio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cadeias_apoio",
    )
    verificacoes = models.JSONField("verificações", default=list, blank=True)
    separacao = models.JSONField("separação das conclusões", default=dict, blank=True)
    confianca = models.CharField("qualidade da sugestão", max_length=20, default="sugerida")
    estado = models.CharField(
        "revisão do vínculo",
        max_length=20,
        choices=EstadoVinculo.choices,
        default=EstadoVinculo.SUGERIDO,
    )
    justificativa = models.TextField("justificativa", blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cadeias_revisadas",
    )
    revisado_em = models.DateTimeField("revisado em", null=True, blank=True)

    class Meta:
        verbose_name = "cadeia de conciliação"
        verbose_name_plural = "cadeias de conciliação"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(fields=["lote", "codigo"], name="cadeia_unica_no_lote"),
        ]

    def __str__(self) -> str:
        return self.titulo


class PendenciaDocumental(models.Model):
    lote = models.ForeignKey(LoteLaboratorio, verbose_name="lote", on_delete=models.CASCADE, related_name="pendencias")
    pagina = models.ForeignKey(
        InventarioPagina,
        verbose_name="página",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendencias",
    )
    regiao = models.ForeignKey(
        RegiaoDocumental,
        verbose_name="peça",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendencias",
    )
    campo = models.ForeignKey(
        CampoExtraido,
        verbose_name="campo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendencias",
    )
    motivo = models.TextField("motivo")
    prioridade = models.CharField(
        "prioridade",
        max_length=20,
        choices=PrioridadePendencia.choices,
        default=PrioridadePendencia.MEDIA,
    )
    status = models.CharField(
        "status",
        max_length=20,
        choices=StatusPendencia.choices,
        default=StatusPendencia.ABERTA,
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendencias_laboratorio",
    )
    solicitacao_esclarecimento = models.TextField("solicitação de esclarecimento preparada", blank=True)
    historico = models.JSONField("histórico", default=list, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pendência documental"
        verbose_name_plural = "pendências documentais"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.motivo[:80]


class RevisaoLaboratorio(models.Model):
    lote = models.ForeignKey(LoteLaboratorio, verbose_name="lote", on_delete=models.CASCADE, related_name="revisoes")
    alvo = models.CharField("alvo da revisão", max_length=40)
    alvo_id = models.PositiveIntegerField("identificador do alvo")
    acao = models.CharField("ação", max_length=60)
    justificativa = models.TextField("justificativa", blank=True)
    detalhe = models.JSONField("detalhe", default=dict, blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revisoes_laboratorio",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "revisão do laboratório"
        verbose_name_plural = "revisões do laboratório"
        ordering = ["-criado_em"]
