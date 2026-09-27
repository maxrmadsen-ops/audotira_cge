"""Agrupa sinalizações pelo vínculo estruturado, não pela semelhança do texto."""

import hashlib

from aplicacao.achados.escolhas import NaturezaAchado, NATUREZA_POR_CATEGORIA, TipoConstatacao


def natureza_da_regra(regra) -> str:
    return NATUREZA_POR_CATEGORIA.get(regra.categoria, NaturezaAchado.OUTRO)


def ancoras_da_execucao(execucao) -> set[str]:
    ancoras = set()
    for referencia in execucao.referencias.all():
        identificador = str(referencia.identificador or "").strip()
        if not identificador.isdigit():
            continue
        if referencia.tipo_fonte in {"despesa", "documento_fiscal", "pagamento", "pessoa", "fornecedor", "item_plano", "meta"}:
            ancoras.add(f"{referencia.tipo_fonte}:{identificador}")
    return ancoras


ORDEM_ANCORA = ("despesa", "documento_fiscal", "pagamento", "fornecedor", "pessoa", "item_plano", "meta")


def ancora_principal(ancoras: set[str]) -> str:
    for tipo in ORDEM_ANCORA:
        encontradas = sorted(ancora for ancora in ancoras if ancora.startswith(f"{tipo}:"))
        if encontradas:
            return encontradas[0]
    return ""


def chave_consolidacao(*, tipo_constatacao: str, natureza: str, ancoras: set[str], codigo_regra: str) -> str:
    principal = ancora_principal(ancoras)
    if principal:
        nucleo = principal
    elif ancoras:
        nucleo = "|".join(sorted(ancoras))
    else:
        nucleo = f"regra:{codigo_regra}"
    bruto = f"{tipo_constatacao}|{natureza}|{nucleo}"
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def mesmo_fato(esquerda: set[str], direita: set[str]) -> bool:
    """Sem âncora compartilhada, textos parecidos não são o mesmo fato."""

    return bool(esquerda and direita and esquerda.intersection(direita))


def tipo_da_sinalizacao(classe: str) -> str:
    if classe == "positiva":
        return TipoConstatacao.CONSTATACAO_POSITIVA
    return TipoConstatacao.ACHADO_POTENCIAL
