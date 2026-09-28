from django.db import models


class TipoDocumento(models.TextChoices):
    TERMO = "termo", "Termo"
    PLANO_TRABALHO = "plano_trabalho", "Plano de trabalho"
    PRESTACAO_PARCIAL = "prestacao_parcial", "Prestação parcial"
    PRESTACAO_FINAL = "prestacao_final", "Prestação final"
    FOLHA_PAGAMENTO = "folha_pagamento", "Folha de pagamento"
    NOTA_FISCAL = "nota_fiscal", "Nota fiscal"
    RECIBO = "recibo", "Recibo"
    COMPROVANTE_BANCARIO = "comprovante_bancario", "Comprovante bancário"
    EXTRATO_BANCARIO = "extrato_bancario", "Extrato bancário"
    GUIA = "guia", "Guia"
    RELATORIO_SIGEF = "relatorio_sigef", "Relatório SIGEF"
    CADASTRO_ENTIDADE = "cadastro_entidade", "Cadastro de entidade"
    RELATORIO_EXECUCAO = "relatorio_execucao", "Relatório de execução"
    DECLARACAO = "declaracao", "Declaração"
    OUTRO = "outro", "Outro"
    NAO_CLASSIFICADO = "nao_classificado", "Não identificado"


class StatusProcessamento(models.TextChoices):
    RECEBIDO = "recebido", "Recebido"
    VALIDANDO = "validando", "Validando"
    PROCESSANDO = "processando", "Processando"
    PROCESSADO = "processado", "Processado"
    AGUARDANDO_VALIDACAO = "aguardando_validacao", "Aguardando validação"
    VALIDADO = "validado", "Validado"
    ERRO = "erro", "Erro"
    ARQUIVADO = "arquivado", "Arquivado"


class EtapaProcessamento(models.TextChoices):
    RECEBIDO = "recebido", "Recebido"
    VALIDANDO_ARQUIVO = "validando_arquivo", "Validando arquivo"
    EXTRAINDO_TEXTO = "extraindo_texto", "Extraindo texto"
    EXECUTANDO_OCR = "executando_ocr", "Executando OCR"
    CLASSIFICANDO = "classificando", "Classificando"
    EXTRAINDO_METADADOS = "extraindo_metadados", "Extraindo metadados"
    AGUARDANDO_VALIDACAO = "aguardando_validacao", "Aguardando validação"
    CONCLUIDO = "concluido", "Concluído"
    ERRO = "erro", "Erro"


class MetodoExtracao(models.TextChoices):
    NATIVO = "nativo", "Nativo"
    OCR = "ocr", "OCR"
    HIBRIDO = "hibrido", "Híbrido"
    SEM_TEXTO = "sem_texto", "Sem texto"


class QualidadeExtracao(models.TextChoices):
    SUFICIENTE = "suficiente", "Suficiente"
    INSUFICIENTE = "insuficiente", "Insuficiente"
    AUSENTE = "ausente", "Ausente"
    ILEGIVEL = "ilegivel", "Ilegível"


class MetodoClassificacao(models.TextChoices):
    NOME_ARQUIVO = "nome_arquivo", "Nome do arquivo"
    PALAVRAS_CHAVE = "palavras_chave", "Palavras-chave"
    HEURISTICA = "heuristica", "Heurística"
    ESTRUTURAL = "estrutural", "Evidência estrutural"
    HUMANO = "humano", "Validação humana"
    NENHUM = "nenhum", "Nenhum"


class OrigemDocumento(models.TextChoices):
    UPLOAD = "upload", "Upload"
    DEMONSTRACAO = "demonstracao", "Demonstração"


class TipoDadoExtraido(models.TextChoices):
    DATA = "data", "Data candidata"
    CPF = "cpf", "CPF candidato"
    CNPJ = "cnpj", "CNPJ candidato"
    VALOR_MONETARIO = "valor_monetario", "Valor monetário candidato"
    NUMERO_DOCUMENTO = "numero_documento", "Número de documento candidato"
    NUMERO_PROCESSO = "numero_processo", "Número de processo candidato"
    NUMERO_INSTRUMENTO = "numero_instrumento", "Número de instrumento candidato"
