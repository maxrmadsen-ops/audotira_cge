import re
import unicodedata
from decimal import Decimal

from django.conf import settings

from aplicacao.documentos.escolhas import MetodoClassificacao, TipoDocumento


SINAIS = (
    (TipoDocumento.NOTA_FISCAL, ("nota fiscal", "danfe", "nf-e", "nfe")),
    (TipoDocumento.FOLHA_PAGAMENTO, ("folha de pagamento", "holerite", "contra cheque", "contracheque")),
    (TipoDocumento.EXTRATO_BANCARIO, ("extrato bancario", "extrato da conta")),
    (TipoDocumento.COMPROVANTE_BANCARIO, ("comprovante bancario", "comprovante de pagamento", "comprovante de transferencia")),
    (TipoDocumento.PLANO_TRABALHO, ("plano de trabalho",)),
    (TipoDocumento.PRESTACAO_FINAL, ("prestacao final",)),
    (TipoDocumento.PRESTACAO_PARCIAL, ("prestacao parcial",)),
    (TipoDocumento.RELATORIO_SIGEF, ("relatorio sigef", "sigef")),
    (TipoDocumento.RELATORIO_EXECUCAO, ("relatorio de execucao",)),
    (TipoDocumento.CADASTRO_ENTIDADE, ("cadastro de entidade", "cartao cnpj")),
    (TipoDocumento.TERMO, ("termo de fomento", "termo de colaboracao", "termo de convenio")),
    (TipoDocumento.RECIBO, ("recibo",)),
    (TipoDocumento.GUIA, ("guia de recolhimento", "darf", "gps")),
    (TipoDocumento.DECLARACAO, ("declaracao",)),
)


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(caractere for caractere in base if not unicodedata.combining(caractere))
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def classificar(nome_original: str, texto: str) -> dict:
    """Sugere um tipo apenas quando alguma heurística encontra sinal. Caso contrário, não classifica."""
    nome = _normalizar(PathName(nome_original))
    corpo = _normalizar(texto[:20000])
    melhor_tipo = TipoDocumento.NAO_CLASSIFICADO
    melhor_pontos = 0
    melhor_metodo = MetodoClassificacao.NENHUM
    for tipo, sinais in SINAIS:
        no_nome = any(sinal in nome for sinal in sinais)
        no_texto = any(sinal in corpo for sinal in sinais)
        if no_nome and no_texto:
            pontos, metodo = 90, MetodoClassificacao.HEURISTICA
        elif no_texto:
            pontos, metodo = 75, MetodoClassificacao.PALAVRAS_CHAVE
        elif no_nome:
            pontos, metodo = 60, MetodoClassificacao.NOME_ARQUIVO
        else:
            continue
        if pontos > melhor_pontos:
            melhor_tipo, melhor_pontos, melhor_metodo = tipo, pontos, metodo
    confianca = Decimal(melhor_pontos) / Decimal("100")
    minimo = Decimal(str(settings.CLASSIFICACAO_CONFIANCA_MINIMA))
    if melhor_pontos == 0 or confianca < minimo:
        return {
            "tipo": TipoDocumento.NAO_CLASSIFICADO,
            "confianca": confianca if melhor_pontos else Decimal("0.000"),
            "metodo": MetodoClassificacao.NENHUM,
        }
    return {"tipo": melhor_tipo, "confianca": confianca, "metodo": melhor_metodo}


def PathName(nome: str) -> str:
    return (nome or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
