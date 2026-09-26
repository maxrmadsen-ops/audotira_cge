from django.db import models


class TipoNorma(models.TextChoices):
    LEI = "lei", "Lei"
    DECRETO = "decreto", "Decreto"
    INSTRUCAO_NORMATIVA = "instrucao_normativa", "Instrução normativa"
    PORTARIA = "portaria", "Portaria"
    RESOLUCAO = "resolucao", "Resolução"
    ORIENTACAO_TECNICA = "orientacao_tecnica", "Orientação técnica"
    MANUAL = "manual", "Manual"
    EDITAL = "edital", "Edital"
    TERMO = "termo", "Termo"
    OUTRO = "outro", "Outro"


class Esfera(models.TextChoices):
    UNIAO = "uniao", "União"
    ESTADO = "estado", "Estado"
    MUNICIPIO = "municipio", "Município"
    OUTRO = "outro", "Outro"


class SituacaoNorma(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    REVOGADA = "revogada", "Revogada"
    SUBSTITUIDA = "substituida", "Substituída"
    ALTERADA = "alterada", "Alterada"


class TipoRelacionamentoNorma(models.TextChoices):
    ALTERA = "altera", "Altera"
    REVOGA = "revoga", "Revoga"
    SUBSTITUI = "substitui", "Substitui"
    REGULAMENTA = "regulamenta", "Regulamenta"
    COMPLEMENTA = "complementa", "Complementa"
    REFERENCIA = "referencia", "Referencia"


class StatusProcessamentoNorma(models.TextChoices):
    RECEBIDA = "recebida", "Recebida"
    VALIDANDO = "validando", "Validando"
    EXTRAINDO = "extraindo", "Extraindo texto"
    SEGMENTANDO = "segmentando", "Segmentando"
    INDEXANDO = "indexando", "Indexando"
    DISPONIVEL = "disponivel", "Disponível"
    ERRO = "erro", "Erro"


class MetodoSegmentacao(models.TextChoices):
    ESTRUTURA_JURIDICA = "estrutura_juridica", "Estrutura jurídica"
    JANELA_TEXTUAL = "janela_textual", "Janela textual"


class MetodoRecuperacao(models.TextChoices):
    LEXICAL = "lexical", "Lexical"
    VETORIAL = "vetorial", "Vetorial"
    HIBRIDO = "hibrido", "Híbrido"
