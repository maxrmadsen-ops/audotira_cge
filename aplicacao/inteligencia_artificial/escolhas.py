from django.db import models

CONCLUSOES_VEDADAS_IA = frozenset({"REGULAR", "IRREGULAR", "APROVADO", "REPROVADO"})
RESULTADO_PRE_IA = "REQUER ANÁLISE SEMÂNTICA"
ERRO_CONTROLADO = "ERRO_CONTROLADO"

CHAVES_GROUND_TRUTH = frozenset(
    {
        "ground_truth",
        "resultado_tecnico_conhecido",
        "parecer_anterior",
        "classificacao_acerto",
        "resposta_esperada",
        "comparacao_ia_tecnico",
    }
)

ERROS_COM_FALLBACK = frozenset(
    {"timeout", "indisponibilidade", "rate_limit", "erro_transitorio", "schema_invalido", "nao_configurado"}
)


class ProvedorIA(models.TextChoices):
    OPENAI = "openai", "OpenAI"
    ANTHROPIC = "anthropic", "Anthropic"
    SIMULADO = "simulado", "Simulado"


class FinalidadeModelo(models.TextChoices):
    ANALISE_SEMANTICA = "analise_semantica", "Análise semântica"
    LABORATORIO = "laboratorio", "Laboratório"
    GERAL = "geral", "Geral"


class StatusUso(models.TextChoices):
    SUCESSO = "sucesso", "Sucesso"
    ERRO_CONTROLADO = "erro_controlado", "Erro controlado"
    INCONCLUSIVO = "inconclusivo", "Inconclusivo"
    LIMITE_EXCEDIDO = "limite_excedido", "Limite excedido"


class EscopoLimite(models.TextChoices):
    CHAMADA = "chamada", "Por chamada"
    DIARIO = "diario", "Diário"
    ANALISE = "analise", "Por análise"
    USUARIO = "usuario", "Por usuário"
    PROVEDOR = "provedor", "Por provedor"


class UnidadePrecificacao(models.TextChoices):
    MILHAO_TOKENS = "1000000", "1 milhão de tokens"
    MIL_TOKENS = "1000", "1 mil tokens"
