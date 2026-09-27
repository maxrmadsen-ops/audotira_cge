from django.db import models

EXPRESSOES_CONCLUSIVAS_VEDADAS = frozenset(
    {
        "FRAUDE",
        "DESVIO",
        "CRIME",
        "CORRUPÇÃO",
        "CORRUPCAO",
        "MÁ-FÉ",
        "MA-FE",
        "MÁ FÉ",
    }
)


class TipoEvidencia(models.TextChoices):
    DOCUMENTAL = "documental", "Documental"
    ESTRUTURADA = "estruturada", "Estruturada"
    CALCULADA = "calculada", "Calculada"
    NORMATIVA = "normativa", "Normativa"
    CRUZAMENTO = "cruzamento", "Cruzamento"
    SEMANTICA_IA = "semantica_ia", "Semântica de IA"
    HUMANA = "humana", "Humana"


class PapelEvidencia(models.TextChoices):
    SUPORTA = "suporta", "Suporta"
    CONTRADIZ = "contradiz", "Contradiz"
    CONTEXTUALIZA = "contextualiza", "Contextualiza"
    AUSENCIA = "ausencia", "Ausência"
    FUNDAMENTA = "fundamenta", "Fundamenta"


class ConfiabilidadeOrigem(models.TextChoices):
    ALTA = "alta", "Alta"
    MEDIA = "media", "Média"
    BAIXA = "baixa", "Baixa"
    NAO_AVALIADA = "nao_avaliada", "Não avaliada"


class StatusValidacaoEvidencia(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    VALIDADA = "validada", "Validada"
    REJEITADA = "rejeitada", "Rejeitada"


class MetodoObtencao(models.TextChoices):
    EXTRACAO = "extracao", "Extração"
    CALCULO = "calculo", "Cálculo"
    CRUZAMENTO = "cruzamento", "Cruzamento"
    AGENTE = "agente", "Agente"
    USUARIO = "usuario", "Usuário"
    NORMA = "norma", "Norma"
    MOTOR = "motor", "Motor"


class StatusAchado(models.TextChoices):
    POTENCIAL = "potencial", "Potencial"
    EM_REVISAO = "em_revisao", "Em revisão"
    CONFIRMADO = "confirmado", "Confirmado"
    DESCARTADO = "descartado", "Descartado"
    AJUSTADO = "ajustado", "Ajustado"
    NECESSITA_DILIGENCIA = "necessita_diligencia", "Necessita diligência"


class NaturezaAchado(models.TextChoices):
    DOCUMENTAL = "documental", "Documental"
    FINANCEIRO = "financeiro", "Financeiro"
    TEMPORAL = "temporal", "Temporal"
    BANCARIO = "bancario", "Bancário"
    PLANO_TRABALHO = "plano_trabalho", "Plano de trabalho"
    VEDACAO = "vedacao", "Vedação"
    OBJETO_META = "objeto_meta", "Objeto e meta"
    CONTRAPARTIDA = "contrapartida", "Contrapartida"
    DEVOLUCAO = "devolucao", "Devolução"
    NORMATIVO = "normativo", "Normativo"
    OUTRO = "outro", "Outro"


class TipoConstatacao(models.TextChoices):
    ACHADO_POTENCIAL = "achado_potencial", "Achado potencial"
    CONSTATACAO_POSITIVA = "constatacao_positiva", "Constatação positiva"


class OrigemGeracao(models.TextChoices):
    DETERMINISTICA = "deterministica", "Determinística"
    IA = "ia", "IA"
    HUMANA = "humana", "Humana"
    MISTA = "mista", "Mista"


class Criticidade(models.TextChoices):
    INFORMATIVA = "informativa", "Informativa"
    BAIXA = "baixa", "Baixa"
    MEDIA = "media", "Média"
    ALTA = "alta", "Alta"
    CRITICA = "critica", "Crítica"


class Prioridade(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    NORMAL = "normal", "Normal"
    ALTA = "alta", "Alta"
    URGENTE = "urgente", "Urgente"


class AcaoRevisao(models.TextChoices):
    CONFIRMAR = "confirmar", "Confirmar"
    DESCARTAR = "descartar", "Descartar"
    AJUSTAR = "ajustar", "Ajustar"
    SOLICITAR_DILIGENCIA = "solicitar_diligencia", "Solicitar diligência"
    MANTER_EM_ANALISE = "manter_em_analise", "Manter em análise"


NATUREZA_POR_CATEGORIA = {
    "Documentação": NaturezaAchado.DOCUMENTAL,
    "Despesas": NaturezaAchado.FINANCEIRO,
    "Pagamentos": NaturezaAchado.FINANCEIRO,
    "Financeiro": NaturezaAchado.FINANCEIRO,
    "Nota fiscal": NaturezaAchado.FINANCEIRO,
    "Bancário": NaturezaAchado.BANCARIO,
    "Prazo": NaturezaAchado.TEMPORAL,
    "Plano de Trabalho": NaturezaAchado.PLANO_TRABALHO,
    "Vedações": NaturezaAchado.VEDACAO,
    "Objeto e Metas": NaturezaAchado.OBJETO_META,
    "Contrapartida": NaturezaAchado.CONTRAPARTIDA,
    "Devolução": NaturezaAchado.DEVOLUCAO,
    "Cláusulas": NaturezaAchado.NORMATIVO,
    "Princípios": NaturezaAchado.NORMATIVO,
}
