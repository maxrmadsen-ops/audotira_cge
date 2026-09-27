"""Nenhuma afirmação material entra na versão oficial sem fonte verificável."""

import re
from dataclasses import dataclass

from aplicacao.inteligencia_artificial.escolhas import CHAVES_GROUND_TRUTH
from aplicacao.pareceres.escolhas import ENC_VEDADOS, StatusValidacaoAfirmacao

CODIGO = re.compile(r"\b[A-Z]{2,4}-\d+\b")
PAGINA = re.compile(r"p[áa]gina\s+(\d+)", re.IGNORECASE)
VALOR = re.compile(r"\d+[.,]\d{2}")
DECISAO = re.compile(r"\b(APROVAD[OA]|REPROVAD[OA]|IRREGULAR)\b|presta[cç][aã]o[^.]{0,40}\bregular\b", re.IGNORECASE)


@dataclass
class ResultadoValidacao:
    status: str
    motivo: str = ""
    fontes_aceitas: list | None = None


class ValidadorProvenienciaPreAnalise:
    def __init__(self, contexto: dict):
        self.contexto = contexto
        self.catalogo = {}
        for item in contexto.get("itens") or []:
            self.catalogo.setdefault(item.get("identificador"), item)
        self.numeros = set(contexto.get("numeros_conhecidos") or [])
        self.paginas = {int(pagina) for pagina in contexto.get("paginas_conhecidas") or [] if str(pagina).isdigit()}
        self.prestacao_id = None
        for item in contexto.get("itens") or []:
            if item.get("prestacao_id"):
                self.prestacao_id = item["prestacao_id"]
                break

    def validar_afirmacao(self, texto: str, tipo: str, fontes: list) -> ResultadoValidacao:
        bruto = texto or ""
        if self._decisao_vedada(bruto) or any(chave in bruto.casefold() for chave in CHAVES_GROUND_TRUTH):
            return ResultadoValidacao(StatusValidacaoAfirmacao.REJEITADA, "Conclusão ou dado isolado não permitido.")
        if self._valor_inventado(bruto) or self._pagina_inventada(bruto) or self._codigo_inventado(bruto, fontes):
            return ResultadoValidacao(StatusValidacaoAfirmacao.REJEITADA, "Valor, página ou código ausente das fontes estruturadas.")
        aceitas = []
        for fonte in fontes or []:
            codigo = fonte if isinstance(fonte, str) else fonte.get("identificador")
            item = self.catalogo.get(codigo)
            if item is None:
                return ResultadoValidacao(StatusValidacaoAfirmacao.REJEITADA, f"Fonte inexistente: {codigo}")
            if item.get("prestacao_id") and self.prestacao_id and item["prestacao_id"] != self.prestacao_id:
                return ResultadoValidacao(StatusValidacaoAfirmacao.REJEITADA, "Fonte de outra prestação.")
            if item.get("tipo") == "norma" and item.get("vigente") is False:
                return ResultadoValidacao(StatusValidacaoAfirmacao.REJEITADA, "Norma fora da vigência.")
            aceitas.append(item)
        if tipo in {"fato", "calculo", "achado", "constatacao_positiva", "fundamentacao"} and not aceitas:
            return ResultadoValidacao(StatusValidacaoAfirmacao.NAO_SUPORTADA, "Afirmação material sem fonte.")
        return ResultadoValidacao(StatusValidacaoAfirmacao.VALIDADA, fontes_aceitas=aceitas)

    def encaminhamento_permitido(self, valor: str) -> bool:
        from aplicacao.pareceres.escolhas import EncaminhamentoPreAnalise

        return valor in EncaminhamentoPreAnalise.values and valor not in ENC_VEDADOS

    def _decisao_vedada(self, texto: str) -> bool:
        return bool(DECISAO.search(texto))

    def _valor_inventado(self, texto: str) -> bool:
        for encontrado in VALOR.findall(texto):
            normalizado = encontrado.replace(",", ".")
            if encontrado not in self.numeros and normalizado not in self.numeros and normalizado + "0" not in self.numeros:
                return True
        return False

    def _pagina_inventada(self, texto: str) -> bool:
        for pagina in PAGINA.findall(texto):
            if int(pagina) not in self.paginas:
                return True
        return False

    def _codigo_inventado(self, texto: str, fontes: list) -> bool:
        citados = set(CODIGO.findall(texto))
        for fonte in fontes or []:
            codigo = fonte if isinstance(fonte, str) else str(fonte.get("identificador") or "")
            citados.add(codigo)
        for codigo in citados:
            if codigo and codigo not in self.catalogo and codigo not in self.numeros:
                return True
        return False
