from django.db import models


class PapelParte(models.TextChoices):
    CONCEDENTE = "concedente", "Concedente"
    BENEFICIARIO = "beneficiario", "Beneficiário"


class CategoriaClausula(models.TextChoices):
    OBJETO = "objeto", "Objeto"
    RECURSOS = "recursos", "Recursos"
    OBRIGACOES_CONCEDENTE = "obrigacoes_concedente", "Obrigações do concedente"
    OBRIGACOES_CONVENENTE = "obrigacoes_convenente", "Obrigações do convenente"
    TEMPORAL = "temporal", "Temporal"
    FINANCEIRA = "financeira", "Financeira"
    PRESTACAO_CONTAS = "prestacao_contas", "Prestação de contas"
    FISCALIZACAO = "fiscalizacao", "Fiscalização"
    RESCISAO = "rescisao", "Rescisão"
    PENALIDADE = "penalidade", "Penalidade"
    VIGENCIA = "vigencia", "Vigência"
    APLICACAO_FINANCEIRA = "aplicacao_financeira", "Aplicação financeira"
    CONTA_BANCARIA = "conta_bancaria", "Conta bancária"
    OUTRA = "outra", "Outra"


class CategoriaObrigacao(models.TextChoices):
    FINANCEIRA = "financeira", "Financeira"
    TEMPORAL = "temporal", "Temporal"
    DOCUMENTAL = "documental", "Documental"
    OPERACIONAL = "operacional", "Operacional"
    CADASTRAL = "cadastral", "Cadastral"
    PRESTACAO_CONTAS = "prestacao_contas", "Prestação de contas"
    APLICACAO_FINANCEIRA = "aplicacao_financeira", "Aplicação financeira"
    CONTA_BANCARIA = "conta_bancaria", "Conta bancária"
    PUBLICIDADE = "publicidade", "Publicidade"
    FISCALIZACAO = "fiscalizacao", "Fiscalização"
    DEVOLUCAO = "devolucao", "Devolução"
    COMUNICACAO = "comunicacao", "Comunicação"
    EXECUCAO_OBJETO = "execucao_objeto", "Execução do objeto"
    OUTRA = "outra", "Outra"


class UnidadeTemporal(models.TextChoices):
    DIAS_CORRIDOS = "dias_corridos", "Dias corridos"
    DIAS_UTEIS = "dias_uteis", "Dias úteis"
    MESES = "meses", "Meses"
    ANOS = "anos", "Anos"


class OperadorTemporal(models.TextChoices):
    ATE = "ate", "Até"
    ANTES_DE = "antes_de", "Antes de"
    APOS = "apos", "Após"
    DENTRO_DE = "dentro_de", "Dentro de"
    ENTRE = "entre", "Entre"
    DURANTE = "durante", "Durante"
    A_PARTIR_DE = "a_partir_de", "A partir de"


class SituacaoExpectativa(models.TextChoices):
    NAO_VERIFICAVEL = "nao_verificavel", "Não verificável nesta etapa"
    PENDENTE = "pendente", "Pendente"
    CUMPRIDO = "cumprido", "Cumprido"
    DESCUMPRIDO = "descumprido", "Descumprido"


class StatusValidacaoTermo(models.TextChoices):
    EXTRAIDO = "extraido", "Extraído"
    AGUARDANDO_VALIDACAO = "aguardando_validacao", "Aguardando validação"
    EM_VALIDACAO = "em_validacao", "Em validação"
    VALIDADO = "validado", "Validado"
    VALIDADO_COM_RESSALVAS = "validado_com_ressalvas", "Validado com ressalvas"
    REJEITADO = "rejeitado", "Rejeitado"


class StatusCampo(models.TextChoices):
    EXTRAIDO = "extraido", "Extraído"
    AGUARDANDO = "aguardando_validacao", "Pendente de validação"
    VALIDADO = "validado", "Validado"
    CORRIGIDO = "corrigido", "Corrigido pelo humano"
    NAO_IDENTIFICADO = "nao_identificado", "Não identificado"
    REJEITADO = "rejeitado", "Rejeitado"


class StatusCorrespondenciaNorma(models.TextChoices):
    NAO_CONFRONTADA = "nao_confrontada", "Não confrontada com o catálogo"
    CORRESPONDENTE = "correspondente", "Correspondente"
    SEM_CORRESPONDENCIA = "sem_correspondencia", "Sem correspondência no catálogo"
