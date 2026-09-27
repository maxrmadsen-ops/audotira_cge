from django.db import models

REGRA_DE_OURO = (
    "A IA deve apontar fatos, evidências, cruzamentos e possíveis inconsistências; a conclusão cabe ao analista."
)
FONTE_EXCLUIDA_TESTE_CEGO = "FONTE_EXCLUIDA_TESTE_CEGO"
CONCLUSOES_VEDADAS = frozenset({"REGULAR", "IRREGULAR", "APROVADO", "REPROVADO"})
RESULTADO_SEMANTICO = "REQUER ANÁLISE SEMÂNTICA"
SINTESE_NAO_CONCLUSIVA = "NÃO CONCLUSIVO"

ORDEM_CATEGORIAS = (
    "Contexto",
    "Documentação",
    "Despesas",
    "Pagamentos",
    "Financeiro",
    "Bancário",
    "Nota fiscal",
    "Vedações",
    "Cláusulas",
    "Prazo",
    "Plano de Trabalho",
    "Princípios",
    "Objeto e Metas",
    "Eficácia/efetividade",
    "Preços",
    "Contrapartida",
    "Devolução",
    "Achados",
    "Governança da IA",
)


class TipoExecucaoTecnica(models.TextChoices):
    DETERMINISTICA = "deterministica", "Determinística"
    DOCUMENTAL = "documental", "Documental"
    SEMANTICA = "semantica", "Semântica"
    HUMANA = "humana", "Humana"
    GOVERNANCA = "governanca", "Governança"
    FORA_ESCOPO_V1 = "fora_escopo_v1", "Fora do escopo da V1"


class CapacidadeExecucao(models.TextChoices):
    AUTOMATICA = "automatica", "Automática"
    PARCIAL = "parcial", "Parcial"
    REQUER_IA = "requer_ia", "Requer IA"
    REQUER_ANALISTA = "requer_analista", "Requer analista"
    FORA_ESCOPO = "fora_escopo", "Fora do escopo"


class StatusTecnico(models.TextChoices):
    SUCESSO = "sucesso", "Sucesso"
    ATENCAO = "atencao", "Atenção"
    DIVERGENCIA = "divergencia", "Divergência"
    INCONCLUSIVO = "inconclusivo", "Inconclusivo"
    NAO_APLICAVEL = "nao_aplicavel", "Não aplicável"
    NAO_EXECUTADA = "nao_executada", "Não executada"
    ERRO = "erro", "Erro"


class Encaminhamento(models.TextChoices):
    NENHUM = "nenhum", "Nenhum"
    REQUER_IA = "requer_ia", "Requer IA"
    REQUER_ANALISTA = "requer_analista", "Requer analista"


class TipoDependencia(models.TextChoices):
    REQUER_SUCESSO = "requer_sucesso", "Requer sucesso"
    REQUER_RESULTADO = "requer_resultado", "Requer resultado"
    BLOQUEIA = "bloqueia", "Bloqueia"
    CONDICIONA = "condiciona", "Condiciona"


class ModoExecucao(models.TextChoices):
    NORMAL = "normal", "Normal"
    TESTE_CEGO = "teste_cego", "Teste cego"


class StatusAnalise(models.TextChoices):
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    AGUARDANDO_VALIDACAO = "aguardando_validacao", "Aguardando validação"
    ERRO = "erro", "Erro"


class EtapaAnalise(models.TextChoices):
    PREPARANDO_CONTEXTO = "preparando_contexto", "Preparando contexto"
    VERIFICANDO_APLICABILIDADE = "verificando_aplicabilidade", "Verificando aplicabilidade"
    RESOLVENDO_NORMAS = "resolvendo_normas", "Resolvendo normas"
    EXECUTANDO_REGRAS = "executando_regras", "Executando regras"
    REGISTRANDO_CALCULOS = "registrando_calculos", "Registrando cálculos"
    REGISTRANDO_LIMITACOES = "registrando_limitacoes", "Registrando limitações"
    AGUARDANDO_VALIDACAO = "aguardando_validacao", "Aguardando validação"
    ERRO = "erro", "Erro"
