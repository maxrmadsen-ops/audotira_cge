from django.db import models


class StatusPreAnalise(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    GERANDO = "gerando", "Gerando"
    AGUARDANDO_REVISAO = "aguardando_revisao", "Aguardando revisão"
    EM_REVISAO = "em_revisao", "Em revisão"
    REVISADA = "revisada", "Revisada"
    CONGELADA = "congelada", "Congelada"
    ERRO = "erro", "Erro"


class TipoSecao(models.TextChoices):
    IDENTIFICACAO = "identificacao", "Identificação"
    ESCOPO_ANALISE = "escopo_analise", "Escopo da análise"
    DOCUMENTACAO_ANALISADA = "documentacao_analisada", "Documentação analisada"
    REFERENCIAL_NORMATIVO = "referencial_normativo", "Referencial normativo"
    VERIFICACOES_REALIZADAS = "verificacoes_realizadas", "Verificações realizadas"
    ACHADOS_CONSTATACOES = "achados_constatacoes", "Achados e constatações"
    LIMITACOES = "limitacoes", "Limitações"
    PONTOS_AVALIACAO_HUMANA = "pontos_avaliacao_humana", "Pontos para avaliação humana"
    SINTESE = "sintese", "Síntese"
    ENCAMINHAMENTO = "encaminhamento", "Encaminhamento"


class TipoAfirmacao(models.TextChoices):
    FATO = "fato", "Fato"
    CALCULO = "calculo", "Cálculo"
    ACHADO = "achado", "Achado"
    CONSTATACAO_POSITIVA = "constatacao_positiva", "Constatação positiva"
    FUNDAMENTACAO = "fundamentacao", "Fundamentação"
    LIMITACAO = "limitacao", "Limitação"
    ENCAMINHAMENTO = "encaminhamento", "Encaminhamento"
    CONTEXTO = "contexto", "Contexto"


class StatusValidacaoAfirmacao(models.TextChoices):
    VALIDADA = "validada", "Validada"
    PARCIALMENTE_SUPORTADA = "parcialmente_suportada", "Parcialmente suportada"
    NAO_SUPORTADA = "nao_suportada", "Não suportada"
    REJEITADA = "rejeitada", "Rejeitada"


class EncaminhamentoPreAnalise(models.TextChoices):
    PROSSEGUIR_ANALISE = "prosseguir_analise", "Prosseguir a análise"
    SOLICITAR_DILIGENCIA = "solicitar_diligencia", "Solicitar diligência"
    SOLICITAR_DOCUMENTACAO = "solicitar_documentacao", "Solicitar documentação"
    SUBMETER_AO_AUDITOR = "submeter_ao_auditor", "Submeter ao auditor"
    REAVALIAR_ACHADO = "reavaliar_achado", "Reavaliar achado"
    SEM_ENCAMINHAMENTO_AUTOMATICO = "sem_encaminhamento_automatico", "Sem encaminhamento automático"


class AcaoRevisaoPreAnalise(models.TextChoices):
    ACEITAR = "aceitar", "Aceitar"
    AJUSTAR = "ajustar", "Ajustar"
    REJEITAR = "rejeitar", "Rejeitar"
    SOLICITAR_NOVA_GERACAO = "solicitar_nova_geracao", "Solicitar nova geração"
    CONGELAR = "congelar", "Congelar"


class OrigemConteudo(models.TextChoices):
    DETERMINISTICO = "deterministico", "Determinístico"
    IA = "ia", "Redigido por IA"
    HUMANO = "humano", "Alterado por humano"


ORDEM_SECAO = {tipo: indice for indice, tipo in enumerate(TipoSecao.values, start=1)}

ENC_VEDADOS = frozenset({"APROVAR", "REPROVAR", "JULGAR_REGULAR", "JULGAR_IRREGULAR"})
