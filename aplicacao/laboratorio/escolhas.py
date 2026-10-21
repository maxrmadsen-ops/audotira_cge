from django.db import models


class EstadoClassificacao(models.TextChoices):
    INCONCLUSIVO = "inconclusivo", "Sem classificação conclusiva"
    PROPOSTO = "proposto", "Proposta automática"
    CONFIRMADO = "confirmado", "Classificação confirmada"
    CORRIGIDO = "corrigido", "Classificação corrigida"


class EstadoRevisao(models.TextChoices):
    PENDENTE = "pendente", "Revisão pendente"
    REVISADA = "revisada", "Revisão registrada"
    ILEGIVEL = "ilegivel", "Marcada como ilegível"
    REPROCESSAR = "reprocessar", "Reprocessamento solicitado"


class EstadoCampo(models.TextChoices):
    PENDENTE = "pendente", "Extração pendente de revisão"
    CONFIRMADO = "confirmado", "Extração confirmada"
    CORRIGIDO = "corrigido", "Extração corrigida"
    AUSENTE = "ausente", "Não localizado na evidência"
    ILEGIVEL = "ilegivel", "Marcado como ilegível"


class EstadoVinculo(models.TextChoices):
    SUGERIDO = "sugerido", "Vínculo sugerido"
    CONFIRMADO = "confirmado", "Vínculo confirmado"
    REJEITADO = "rejeitado", "Vínculo rejeitado"


class PrioridadePendencia(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    MEDIA = "media", "Média"
    ALTA = "alta", "Alta"


class StatusPendencia(models.TextChoices):
    ABERTA = "aberta", "Aberta"
    EM_PREPARACAO = "em_preparacao", "Solicitação em preparação"
    RESOLVIDA = "resolvida", "Resolvida"


class ConferenciaInstrumento(models.TextChoices):
    PENDENTE = "pendente", "Conferência pendente"
    CONFIRMADA = "confirmada", "Conferência humana registrada"
