"""Validação da saída estruturada. Texto livre não vira resultado."""

from aplicacao.inteligencia_artificial.escolhas import CONCLUSOES_VEDADAS_IA

CAMPOS_OBRIGATORIOS = (
    "resultado",
    "justificativa_resumida",
    "fatos_identificados",
    "fontes_utilizadas",
    "fundamentos_normativos",
    "limitacoes",
    "dados_insuficientes",
    "requer_revisao_humana",
)


class SchemaInvalido(Exception):
    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


class RespostaIncompleta(Exception):
    codigo = "resposta_incompleta"

    def __init__(self, diagnostico: list[str] | None = None):
        self.diagnostico = list(diagnostico or ["resposta_vazia"])[:12]
        super().__init__(self.codigo)


def validar_schema(payload) -> dict:
    if not isinstance(payload, dict):
        raise SchemaInvalido("A resposta não é um objeto.")
    ausentes = [campo for campo in CAMPOS_OBRIGATORIOS if campo not in payload]
    if ausentes:
        raise SchemaInvalido("Campos ausentes: " + ", ".join(ausentes))
    if not isinstance(payload["resultado"], str) or not payload["resultado"].strip():
        raise SchemaInvalido("Resultado ausente.")
    if payload["resultado"].strip().upper() in CONCLUSOES_VEDADAS_IA:
        raise SchemaInvalido("Conclusão administrativa vedada.")
    if not isinstance(payload["justificativa_resumida"], str):
        raise SchemaInvalido("Justificativa inválida.")
    for campo in ("fatos_identificados", "fontes_utilizadas", "fundamentos_normativos", "limitacoes"):
        if not isinstance(payload[campo], list):
            raise SchemaInvalido(f"{campo} não é uma lista.")
    if not isinstance(payload["dados_insuficientes"], bool):
        raise SchemaInvalido("dados_insuficientes deve ser booleano.")
    if payload["requer_revisao_humana"] is not True:
        raise SchemaInvalido("A revisão humana é obrigatória.")
    return {
        "resultado": payload["resultado"].strip()[:120],
        "justificativa_resumida": payload["justificativa_resumida"].strip()[:1000],
        "fatos_identificados": payload["fatos_identificados"][:20],
        "fontes_utilizadas": payload["fontes_utilizadas"][:20],
        "fundamentos_normativos": payload["fundamentos_normativos"][:20],
        "limitacoes": [str(item)[:500] for item in payload["limitacoes"][:20]],
        "dados_insuficientes": payload["dados_insuficientes"],
        "requer_revisao_humana": True,
    }
