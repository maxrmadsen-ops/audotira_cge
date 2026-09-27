from dataclasses import dataclass, field
from decimal import Decimal

from aplicacao.regras.escolhas import (
    CONCLUSOES_VEDADAS,
    Encaminhamento,
    StatusTecnico,
)

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")
TOKENS_DIVERGENCIA = {"DIVERGÊNCIA", "FORA DA VIGÊNCIA", "INTEMPESTIVA"}
TOKENS_ATENCAO = {
    "POSSÍVEL VEDAÇÃO",
    "POSSÍVEL INCONSISTÊNCIA",
    "POSSÍVEL INCOMPATIBILIDADE",
    "POSSÍVEL DESCUMPRIMENTO",
    "POSSÍVEL INDÍCIO",
    "POSSÍVEL SALDO NÃO DEVOLVIDO",
    "POSSÍVEL AUSÊNCIA",
    "LACUNA IDENTIFICADA",
    "SEM SUPORTE LOCALIZADO",
    "SEM SUPORTE",
}


@dataclass
class ResultadoExecutor:
    resultado_funcional: str
    status_tecnico: str
    limitacao: str = ""
    referencias: list = field(default_factory=list)
    calculos: list = field(default_factory=list)
    entradas: dict = field(default_factory=dict)
    encaminhamento: str = Encaminhamento.NENHUM


def dinheiro(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    return Decimal(valor).quantize(CENTAVO)


def somar(valores) -> Decimal | None:
    presentes = [dinheiro(valor) for valor in valores if valor is not None and valor != ""]
    if not presentes:
        return None
    return sum(presentes, ZERO)


def percentual(diferenca: Decimal, base: Decimal) -> Decimal | None:
    if base == ZERO:
        return None
    return (diferenca / base * Decimal("100")).quantize(CENTAVO)


def texto_moeda(valor: Decimal) -> str:
    quantized = valor.quantize(CENTAVO)
    sinal = "-" if quantized < 0 else ""
    absoluto = abs(quantized)
    inteiro, centavos = f"{absoluto:.2f}".split(".")
    inteiro_formatado = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}{inteiro_formatado},{centavos}"


def calculo(operacao: str, operandos: dict, resultado: Decimal, unidade: str) -> dict:
    return {
        "operacao": operacao,
        "operandos": {chave: str(valor) for chave, valor in operandos.items()},
        "resultado": str(resultado),
        "unidade": unidade,
    }


def referencia(**dados) -> dict:
    trecho = (dados.get("trecho") or "")[:500]
    return {
        "tipo_fonte": dados.get("tipo_fonte", ""),
        "identificador": str(dados.get("identificador") or ""),
        "documento_id": dados.get("documento_id"),
        "pagina_id": dados.get("pagina_id"),
        "trecho_normativo_id": dados.get("trecho_normativo_id"),
        "trecho": trecho,
        "campo": dados.get("campo") or "",
        "valor_utilizado": str(dados.get("valor_utilizado") or "")[:255],
        "papel_na_regra": dados.get("papel_na_regra") or "",
    }


def status_de(resultado: str, padrao: str | None = None) -> str:
    if padrao:
        return padrao
    if resultado in TOKENS_DIVERGENCIA:
        return StatusTecnico.DIVERGENCIA
    if resultado in TOKENS_ATENCAO:
        return StatusTecnico.ATENCAO
    if resultado in {"NÃO VERIFICÁVEL", "NÃO VALIDÁVEL", "INCOMPLETO", "INSUFICIENTE", "NÃO GERAR"}:
        return StatusTecnico.INCONCLUSIVO
    if resultado in {"NÃO REALIZADA – ESCOPO DA V1", "REQUER ANÁLISE SEMÂNTICA"}:
        return StatusTecnico.NAO_EXECUTADA
    return StatusTecnico.SUCESSO


def conclusao_vedada(resultado: str) -> bool:
    return resultado.strip().upper() in CONCLUSOES_VEDADAS


def agregar(parciais: list[str], *, ok: str, divergencia: str, ausente: str, inconclusivo: str) -> str:
    if not parciais:
        return inconclusivo
    if any(item == divergencia for item in parciais):
        return divergencia
    if all(item == ok for item in parciais):
        return ok
    if any(item == ok for item in parciais):
        return inconclusivo
    if any(item == ausente for item in parciais):
        return ausente
    return inconclusivo
