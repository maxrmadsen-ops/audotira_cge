from django.db import models


class SituacaoPrestacao(models.TextChoices):
    EM_ELABORACAO = "em_elaboracao", "Em elaboração"
    EM_ANALISE = "em_analise", "Em análise"
    CONCLUIDA = "concluida", "Concluída"
    ARQUIVADA = "arquivada", "Arquivada"


class FasePrestacao(models.TextChoices):
    PACTUACAO = "pactuacao", "Pactuação"
    EXECUCAO = "execucao", "Execução"
    PRESTACAO = "prestacao", "Prestação"
    ENCERRADA = "encerrada", "Encerrada"


class TipoInstrumento(models.TextChoices):
    TERMO_FOMENTO = "termo_fomento", "Termo de fomento"
    TERMO_COLABORACAO = "termo_colaboracao", "Termo de colaboração"
    CONVENIO = "convenio", "Convênio"
    CONTRATO = "contrato", "Contrato"
    OUTRO = "outro", "Outro"


class NaturezaItem(models.TextChoices):
    PESSOAL = "pessoal", "Pessoal"
    MATERIAL = "material", "Material"
    SERVICO = "servico", "Serviço"
    ENCARGO = "encargo", "Encargo"
    OUTRO = "outro", "Outro"


class TipoPrestacaoParcial(models.TextChoices):
    PARCIAL = "parcial", "Parcial"
    FINAL = "final", "Final"


class TipoDocumentoFiscal(models.TextChoices):
    NOTA_FISCAL = "nota_fiscal", "Nota fiscal"
    RECIBO = "recibo", "Recibo"
    FATURA = "fatura", "Fatura"
    OUTRO = "outro", "Outro"


class MeioPagamento(models.TextChoices):
    TRANSFERENCIA = "transferencia", "Transferência"
    TED = "ted", "TED"
    PIX = "pix", "Pix"
    CHEQUE = "cheque", "Cheque"
    DINHEIRO = "dinheiro", "Dinheiro"
    OUTRO = "outro", "Outro"


class TipoMovimentacao(models.TextChoices):
    CREDITO = "credito", "Crédito"
    DEBITO = "debito", "Débito"
