"""Tipos de exibição. Ausência permanece explícita e não vira zero."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP


NAO_DISPONIVEL = "Não disponível"
SEM_DADOS = "Sem dados"
SEM_HISTORICO = "Sem dados históricos suficientes."
QUATRO = Decimal("0.0001")
DOIS = Decimal("0.01")


def texto_contagem(valor: int) -> str:
    return str(valor)


def texto_decimal(valor: Decimal | None, casas: Decimal = DOIS) -> str:
    if valor is None:
        return NAO_DISPONIVEL
    return format(Decimal(valor).quantize(casas, rounding=ROUND_HALF_UP), "f")


def taxa(numerador: int, denominador: int) -> str:
    if denominador == 0:
        return NAO_DISPONIVEL
    return texto_decimal(Decimal(numerador) / Decimal(denominador), QUATRO)


@dataclass
class Indicador:
    nome: str
    exibicao: str
    url: str = ""
    observacao: str = ""
    complemento: str = ""
    peso: int = 0


@dataclass
class Serie:
    rotulo: str
    quantidade: int | None
    exibicao: str
    url: str = ""
    percentual: int = 0
    fatia: int = 0
    deslocamento: int = 25
    traco: str = ""


@dataclass
class Grafico:
    titulo: str
    descricao: str
    series: list[Serie] = field(default_factory=list)
    vazio: str = SEM_DADOS
    formato: str = "barras"
    centro: str = ""
    total: int = 0

    @property
    def tem_dados(self) -> bool:
        return any(item.quantidade not in (None, 0) for item in self.series)


def grafico(titulo: str, descricao: str, series: list[Serie], vazio: str, formato: str = "barras", centro: str = "", incluir_zeros: bool = False) -> Grafico:
    escolhidas = list(series) if incluir_zeros else [item for item in series if item.quantidade]
    maior = max((item.quantidade or 0 for item in escolhidas), default=0)
    if maior:
        for item in escolhidas:
            item.percentual = int(round(100 * (item.quantidade or 0) / maior))
    total = sum(item.quantidade or 0 for item in escolhidas)
    if formato == "donut" and total:
        acumulado = 0
        for item in escolhidas:
            fatia = int(round(100 * (item.quantidade or 0) / total))
            item.fatia = fatia
            item.deslocamento = 25 - acumulado
            item.traco = f"{fatia} {max(100 - fatia, 0)}"
            acumulado += fatia
    return Grafico(titulo=titulo, descricao=descricao, series=escolhidas, vazio=vazio, formato=formato, centro=centro, total=total)


@dataclass
class Ocorrencia:
    tipo: str
    descricao: str
    quando: str
    prestacao: str
    criticidade: str
    url: str


@dataclass
class Linha:
    colunas: list[str]
    url: str = ""


@dataclass
class PainelAba:
    kpis: list[Indicador] = field(default_factory=list)
    graficos: list[Grafico] = field(default_factory=list)
    pipeline: list[Indicador] = field(default_factory=list)
    atencao: list[Ocorrencia] = field(default_factory=list)
    colunas: list[str] = field(default_factory=list)
    linhas: list[Linha] = field(default_factory=list)
    historico: Grafico | None = None
    mensagem_historico: str = ""
    avisos: list[str] = field(default_factory=list)
    vazio_tabela: str = SEM_DADOS
    vazio_atencao: str = "Não há situações de atenção no recorte."
