from django.db import models


class ModoGroundTruth(models.TextChoices):
    CEGO = "cego", "Cego"
    ASSISTIDO = "assistido", "Assistido"


class StatusGroundTruth(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    EM_VALIDACAO = "em_validacao", "Em validação"
    VALIDADO = "validado", "Validado"
    CONGELADO = "congelado", "Congelado"


class CriticidadeReferencia(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    MEDIA = "media", "Média"
    ALTA = "alta", "Alta"
    CRITICA = "critica", "Crítica"


class PrioridadeReferencia(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    NORMAL = "normal", "Normal"
    ALTA = "alta", "Alta"
    URGENTE = "urgente", "Urgente"


class SituacaoReferencia(models.TextChoices):
    REGISTRADO = "registrado", "Registrado"
    EM_REVISAO_TECNICA = "em_revisao_tecnica", "Em revisão técnica"


class StatusAvaliacao(models.TextChoices):
    PREPARANDO = "preparando", "Preparando"
    AGUARDANDO_GROUND_TRUTH = "aguardando_ground_truth", "Aguardando Ground Truth"
    COMPARANDO = "comparando", "Comparando"
    AGUARDANDO_REVISAO = "aguardando_revisao", "Aguardando revisão"
    CONCLUIDA = "concluida", "Concluída"
    CONGELADA = "congelada", "Congelada"
    ERRO = "erro", "Erro"


class ClassificacaoCorrespondencia(models.TextChoices):
    VERDADEIRO_POSITIVO = "verdadeiro_positivo", "Verdadeiro positivo"
    FALSO_POSITIVO = "falso_positivo", "Falso positivo"
    FALSO_NEGATIVO = "falso_negativo", "Falso negativo"
    CORRESPONDENCIA_PARCIAL = "correspondencia_parcial", "Correspondência parcial"
    PENDENTE_REVISAO = "pendente_revisao", "Pendente de revisão"


class MetodoCorrespondencia(models.TextChoices):
    DETERMINISTICO = "deterministico", "Determinístico"
    SUGESTAO_SEMANTICA = "sugestao_semantica", "Sugestão semântica"
    REVISAO_HUMANA = "revisao_humana", "Revisão humana"


class AcaoRevisaoCorrespondencia(models.TextChoices):
    CONFIRMAR = "confirmar", "Confirmar"
    REJEITAR = "rejeitar", "Rejeitar"
    AJUSTAR = "ajustar", "Ajustar"
    MARCAR_PARCIAL = "marcar_parcial", "Marcar como parcial"


class AplicabilidadeComparacao(models.TextChoices):
    AVALIAVEL = "avaliavel", "Avaliável"
    NAO_APLICAVEL = "nao_aplicavel", "Não aplicável"
    SEM_GROUND_TRUTH = "sem_ground_truth", "Sem Ground Truth"
    FORA_ESCOPO = "fora_escopo", "Fora do escopo"


CRITICAS = frozenset({CriticidadeReferencia.ALTA, CriticidadeReferencia.CRITICA})
