from django.db.models import TextChoices


class SituacaoDiligencia(TextChoices):
    ABERTA = "aberta", "Aberta"
    AGUARDANDO_RESPOSTA = "aguardando_resposta", "Aguardando resposta"
    RESPONDIDA = "respondida", "Respondida"
    ENCERRADA = "encerrada", "Encerrada"
    CANCELADA = "cancelada", "Cancelada"


class MotivoDiligencia(TextChoices):
    AUSENCIA_DOCUMENTO = "ausencia_documento", "Ausência de documento"
    DOCUMENTO_ILEGIVEL = "documento_ilegivel", "Documento ilegível"
    INFORMACAO_INCOMPLETA = "informacao_incompleta", "Informação incompleta"
    DIVERGENCIA = "divergencia", "Divergência que necessita esclarecimento"
    DOCUMENTO_COMPLEMENTAR = "documento_complementar", "Necessidade de documento complementar"
    OUTRO = "outro", "Outra situação justificada"
