"""Filtros globais limitados a dimensões que existem no modelo."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import date
from urllib.parse import urlencode

from django.urls import reverse


def _data(valor: str) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _inteiro(valor: str) -> int | None:
    if not valor:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class FiltrosPainel:
    inicio: date | None = None
    fim: date | None = None
    prestacao: int | None = None
    situacao: str = ""
    concedente: int | None = None
    beneficiario: int | None = None
    tipo_instrumento: str = ""
    responsavel: int | None = None
    criticidade: str = ""
    categoria: str = ""
    natureza: str = ""
    tipo_documento: str = ""
    regra: int | None = None
    categoria_regra: str = ""
    tipo_execucao: str = ""
    agente: str = ""
    modelo: int | None = None
    provedor: str = ""
    origem: str = ""

    @classmethod
    def da_requisicao(cls, dados) -> "FiltrosPainel":
        return cls(
            inicio=_data(dados.get("inicio", "")),
            fim=_data(dados.get("fim", "")),
            prestacao=_inteiro(dados.get("prestacao", "")),
            situacao=(dados.get("situacao") or "").strip(),
            concedente=_inteiro(dados.get("concedente", "")),
            beneficiario=_inteiro(dados.get("beneficiario", "")),
            tipo_instrumento=(dados.get("tipo_instrumento") or "").strip(),
            responsavel=_inteiro(dados.get("responsavel", "")),
            criticidade=(dados.get("criticidade") or "").strip(),
            categoria=(dados.get("categoria") or "").strip(),
            natureza=(dados.get("natureza") or "").strip(),
            tipo_documento=(dados.get("tipo_documento") or "").strip(),
            regra=_inteiro(dados.get("regra", "")),
            categoria_regra=(dados.get("categoria_regra") or "").strip(),
            tipo_execucao=(dados.get("tipo_execucao") or "").strip(),
            agente=(dados.get("agente") or "").strip(),
            modelo=_inteiro(dados.get("modelo", "")),
            provedor=(dados.get("provedor") or "").strip(),
            origem=(dados.get("origem") or "").strip(),
        )

    def alterar(self, **kwargs) -> "FiltrosPainel":
        return replace(self, **kwargs)

    def pares(self) -> list[tuple[str, str]]:
        saida = []
        for item in fields(self):
            valor = getattr(self, item.name)
            if valor in (None, ""):
                continue
            if isinstance(valor, date):
                saida.append((item.name, valor.isoformat()))
            else:
                saida.append((item.name, str(valor)))
        return saida

    def querystring(self) -> str:
        return urlencode(self.pares())

    def ativos(self) -> list[tuple[str, str, str]]:
        rotulos = {
            "inicio": "Período inicial",
            "fim": "Período final",
            "prestacao": "Prestação",
            "situacao": "Situação",
            "concedente": "Concedente",
            "beneficiario": "Beneficiário",
            "tipo_instrumento": "Tipo de instrumento",
            "responsavel": "Responsável",
            "criticidade": "Criticidade",
            "categoria": "Categoria",
            "natureza": "Natureza",
            "tipo_documento": "Tipo documental",
            "regra": "Regra",
            "categoria_regra": "Categoria da regra",
            "tipo_execucao": "Tipo de execução",
            "agente": "Agente",
            "modelo": "Modelo",
            "provedor": "Provedor",
            "origem": "Origem dos dados",
        }
        ativos = []
        for nome, valor in self.pares():
            restantes = [par for par in self.pares() if par[0] != nome]
            exibicao = "alta ou crítica" if nome == "criticidade" and valor == "alta_ou_critica" else valor
            ativos.append((rotulos.get(nome, nome), exibicao, urlencode(restantes)))
        return ativos


def href(nome_url: str, filtros: FiltrosPainel | None = None, **extra) -> str:
    base = reverse(nome_url)
    if filtros is None and not extra:
        return base
    atual = filtros.alterar(**extra) if filtros is not None else FiltrosPainel().alterar(**extra)
    consulta = atual.querystring()
    return f"{base}?{consulta}" if consulta else base
