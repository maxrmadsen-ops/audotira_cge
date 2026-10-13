from django.conf import settings
from django.db import models

from aplicacao.diligencias.escolhas import MotivoDiligencia, SituacaoDiligencia
from aplicacao.entidades.models import Rastreavel


class Diligencia(Rastreavel):
    """Solicitação formal de manifestação/correção vinculada à prestação."""

    identificador = models.CharField("identificador", max_length=40, unique=True)
    prestacao = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        on_delete=models.PROTECT,
        related_name="diligencias",
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="analista solicitante",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="diligencias_solicitadas",
    )
    motivo = models.CharField("motivo", max_length=40, choices=MotivoDiligencia.choices)
    descricao = models.TextField("descrição")
    documentos = models.ManyToManyField(
        "documentos.Documento",
        verbose_name="documentos relacionados",
        blank=True,
        related_name="diligencias",
    )
    aberta_em = models.DateTimeField("data de abertura", auto_now_add=True)
    prazo = models.DateField("prazo", null=True, blank=True)
    situacao = models.CharField(
        "situação",
        max_length=30,
        choices=SituacaoDiligencia.choices,
        default=SituacaoDiligencia.ABERTA,
        db_index=True,
    )
    resposta = models.TextField("resposta/manifestação", blank=True)
    respondida_em = models.DateTimeField("data de resposta", null=True, blank=True)
    encerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="encerrada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="diligencias_encerradas",
    )
    encerrada_em = models.DateTimeField("encerrada em", null=True, blank=True)

    class Meta:
        verbose_name = "diligência"
        verbose_name_plural = "diligências"
        ordering = ["-aberta_em", "-id"]

    def __str__(self) -> str:
        return self.identificador


class HistoricoDiligencia(models.Model):
    diligencia = models.ForeignKey(
        Diligencia,
        verbose_name="diligência",
        on_delete=models.CASCADE,
        related_name="historico",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="historicos_diligencia",
    )
    situacao_anterior = models.CharField("situação anterior", max_length=30, blank=True)
    situacao_nova = models.CharField("situação nova", max_length=30, blank=True)
    observacao = models.TextField("observação", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "histórico de diligência"
        verbose_name_plural = "históricos de diligência"
        ordering = ["-criado_em", "-id"]
