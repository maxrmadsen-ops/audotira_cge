"""Extração estruturada local por tipo. Não preenche ausência com suposição."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from aplicacao.laboratorio.esquemas import esquema_do_tipo


def _moeda_para_decimal(texto: str) -> Decimal | None:
    limpo = (texto or "").strip()
    if not limpo:
        return None
    limpo = limpo.replace("R$", "").replace(" ", "")
    if "," in limpo and "." in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")
    try:
        return Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None


def texto_moeda(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    formatado = f"{valor:,.2f}"
    return "R$ " + formatado.replace(",", "X").replace(".", ",").replace("X", ".")


def liquido_deterministico(proventos: Decimal | None, descontos: Decimal | None) -> Decimal | None:
    if proventos is None or descontos is None:
        return None
    return proventos - descontos


def _buscar(padroes: tuple[str, ...], texto: str, flags=re.IGNORECASE | re.MULTILINE) -> str:
    for padrao in padroes:
        achado = re.search(padrao, texto or "", flags=flags)
        if achado:
            grupo = achado.group(1) if achado.lastindex else achado.group(0)
            return (grupo or "").strip()
    return ""


def _trecho(texto: str, valor: str, janela: int = 80) -> str:
    if not valor:
        return ""
    pos = (texto or "").lower().find(valor.lower())
    if pos < 0:
        return valor[:janela]
    inicio = max(0, pos - 20)
    fim = min(len(texto), pos + len(valor) + 40)
    return texto[inicio:fim].strip()


def extrair_campos(tipo: str, texto: str, numero_pagina: int, metodo: str) -> list[dict]:
    esquema = esquema_do_tipo(tipo)
    mapeados = _extratores.get(tipo, _extrair_generico)(texto)
    campos = []
    for item in esquema:
        original = mapeados.get(item.chave, "")
        normalizado = original
        if item.chave in {
            "valor",
            "valor_liquido",
            "total_proventos",
            "total_descontos",
            "irrf",
            "inss",
            "salario_base",
            "total_bruto",
            "total_liquido",
            "valor_quitado",
            "valor_recolhimento",
            "liquido_calculado",
            "base_recolhimento",
            "encargos",
            "saldo_inicial",
            "saldo_final",
        }:
            decimal = _moeda_para_decimal(original) if original else None
            if item.chave == "liquido_calculado" and not original:
                decimal = liquido_deterministico(
                    _moeda_para_decimal(mapeados.get("total_proventos", "")),
                    _moeda_para_decimal(mapeados.get("total_descontos", "")),
                )
                original = texto_moeda(decimal) if decimal is not None else ""
            normalizado = str(decimal) if decimal is not None else ""
        campos.append(
            {
                "esquema": tipo,
                "chave": item.chave,
                "rotulo": item.rotulo,
                "valor_original": original,
                "valor_normalizado": normalizado,
                "numero_pagina": numero_pagina,
                "trecho_evidencia": _trecho(texto, original) if original else "",
                "metodo": metodo if original else "nao_localizado",
                "estado_confianca": "evidencia_textual" if original else "ausente",
                "obrigatorio": item.obrigatorio,
            }
        )
    return campos


def _extrair_holerite(texto: str) -> dict[str, str]:
    return {
        "empregador": _buscar((r"(?:empregador|empresa|raz[aã]o social)\s*[:\-]?\s*(.+)",), texto),
        "funcionario": _buscar(
            (r"(?:funcion[aá]rio|empregado|nome do empregado|trabalhador)\s*[:\-]?\s*(.+)",),
            texto,
        ),
        "identificadores": _buscar((r"(?:cpf|matr[ií]cula|pis)\s*[:\-]?\s*([0-9.\-/]+)",), texto),
        "cargo": _buscar((r"(?:cargo|fun[cç][aã]o)\s*[:\-]?\s*(.+)",), texto),
        "competencia": _buscar(
            (
                r"(?:compet[eê]ncia|refer[eê]ncia|m[eê]s/?ano)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{2,4})",
                r"\b((?:0?[1-9]|1[0-2])[/.\-]20[0-9]{2})\b",
            ),
            texto,
        ),
        "data_admissao": _buscar((r"(?:admiss[aã]o|data de admiss[aã]o)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "salario_base": _buscar((r"(?:sal[aá]rio[\s\-]?base|sal[aá]rio)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "total_proventos": _buscar(
            (
                r"(?:total\s+de\s+proventos|proventos)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",
                r"(?:proventos)\s+(R\$\s*[0-9.,]+|[0-9.,]+)",
            ),
            texto,
        ),
        "total_descontos": _buscar(
            (
                r"(?:total\s+de\s+descontos|descontos)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",
            ),
            texto,
        ),
        "valor_liquido": _buscar(
            (
                r"(?:l[ií]quido\s+a\s+receber|valor\s+l[ií]quido|l[ií]quido)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",
            ),
            texto,
        ),
        "irrf": _buscar((r"(?:irrf|i\.?r\.?r\.?f\.?)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "inss": _buscar((r"(?:inss)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "rubricas_proventos": "",
        "rubricas_descontos": "",
        "bases_calculo": "",
        "assinaturas": _buscar((r"(assinatura|carimbo|atesto).{0,40}",), texto),
        "liquido_calculado": "",
    }


def _extrair_comprovante(texto: str) -> dict[str, str]:
    return {
        "instituicao": _buscar((r"(banco\s+[^\n]+|caixa econ[oô]mica|banco do brasil|sicredi|sicoob|bradesco|itau|itaú)",), texto),
        "titular_origem": _buscar((r"(?:titular|nome do pagador|cliente)\s*[:\-]?\s*(.+)",), texto),
        "conta_origem": _buscar((r"(?:conta|ag[eê]ncia/?conta)\s*[:\-]?\s*([0-9\-./]+)",), texto),
        "beneficiario": _buscar((r"(?:favorecido|benefici[aá]rio|destinat[aá]rio)\s*[:\-]?\s*(.+)",), texto),
        "dados_destino": _buscar((r"(?:conta destino|destino)\s*[:\-]?\s*(.+)",), texto),
        "data_hora": _buscar(
            (
                r"([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4}(?:\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)?)",
            ),
            texto,
        ),
        "valor": _buscar((r"(?:valor|valor da transfer[eê]ncia|valor pago)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "tipo_operacao": _buscar((r"(ted|doc|pix|transfer[eê]ncia)",), texto),
        "identificadores": _buscar((r"(?:autentica[cç][aã]o|nsu|id|protocolo)\s*[:\-]?\s*([A-Za-z0-9\-./]+)",), texto),
        "situacao": _buscar((r"(efetivad[ao]|realizad[ao]|confirmad[ao]|rejeitad[ao])",), texto),
    }


def _extrair_rescisao(texto: str) -> dict[str, str]:
    return {
        "empregador": _buscar((r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",), texto),
        "trabalhador": _buscar((r"(?:trabalhador|empregado|funcion[aá]rio)\s*[:\-]?\s*(.+)",), texto),
        "dados_vinculo": "",
        "data_admissao": _buscar((r"(?:admiss[aã]o)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "data_aviso": _buscar((r"(?:aviso)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "data_desligamento": _buscar((r"(?:desligamento|rescis[aã]o|afastamento)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "motivo": _buscar((r"(?:motivo|c[oó]digo de afastamento)\s*[:\-]?\s*(.+)",), texto),
        "verbas_rescisorias": "",
        "deducoes": "",
        "total_bruto": _buscar((r"(?:total bruto|bruto)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "total_liquido": _buscar((r"(?:total l[ií]quido|l[ií]quido)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "assinaturas": _buscar((r"(assinatura|quitação|quitacao).{0,40}",), texto),
    }


def _extrair_quitacao(texto: str) -> dict[str, str]:
    return {
        "empregador": _buscar((r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",), texto),
        "trabalhador": _buscar((r"(?:trabalhador|empregado|funcion[aá]rio)\s*[:\-]?\s*(.+)",), texto),
        "valor_quitado": _buscar((r"(?:valor|total)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "data": _buscar((r"([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "assinaturas": _buscar((r"(assinatura|quitação|quitacao).{0,40}",), texto),
    }


def _extrair_dispensa(texto: str) -> dict[str, str]:
    return {
        "empregador": _buscar((r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",), texto),
        "trabalhador": _buscar((r"(?:trabalhador|empregado|funcion[aá]rio|sr[a]?\.?)\s*[:\-]?\s*(.+)",), texto),
        "data_comunicacao": _buscar((r"([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "motivo": _buscar((r"(?:motivo|dispensa)\s*[:\-]?\s*(.+)",), texto),
        "comprovante_recebimento": _buscar((r"(recebi|ciente|protocolo|ar\b).{0,40}",), texto),
    }


def _extrair_fgts(texto: str) -> dict[str, str]:
    return {
        "competencia": _buscar((r"(?:compet[eê]ncia)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "empregador": _buscar((r"(?:empregador|raz[aã]o social|cnpj)\s*[:\-]?\s*(.+)",), texto),
        "tipo_guia": _buscar((r"(grf|grrf|guia de recolhimento)",), texto),
        "base_recolhimento": _buscar((r"(?:base(?:\s+de)?\s+c[aá]lculo|base)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "valor_recolhimento": _buscar((r"(?:valor(?:\s+do)?\s+recolhimento|valor\s+total|valor)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "encargos": _buscar((r"(?:encargos|juros|multa)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "vencimento": _buscar((r"(?:vencimento)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "data_pagamento": _buscar((r"(?:pagamento|pago em)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "autenticacao": _buscar((r"(?:autentica[cç][aã]o|autentica[cç][aã]o banc[aá]ria)\s*[:\-]?\s*([A-Za-z0-9\-./]+)",), texto),
        "abrangencia": _buscar((r"(coletiv[oa]|individual)",), texto),
    }


def _extrair_generico(texto: str) -> dict[str, str]:
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    titulo = linhas[0][:120] if linhas else ""
    return {"titulo": titulo, "observacao": "", "identificador": "", "data": "", "periodo": "", "totais": ""}


_extratores = {
    "holerite": _extrair_holerite,
    "comprovante_transferencia": _extrair_comprovante,
    "termo_rescisao": _extrair_rescisao,
    "termo_quitacao": _extrair_quitacao,
    "comunicacao_dispensa": _extrair_dispensa,
    "guia_fgts": _extrair_fgts,
    "comprovante_fgts": _extrair_fgts,
    "extrato_bancario": lambda texto: {
        "instituicao": _buscar((r"(banco\s+[^\n]+)",), texto),
        "titular": _buscar((r"(?:titular|cliente)\s*[:\-]?\s*(.+)",), texto),
        "periodo": _buscar((r"(?:per[ií]odo)\s*[:\-]?\s*(.+)",), texto),
        "saldo_inicial": _buscar((r"(?:saldo anterior|saldo inicial)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "saldo_final": _buscar((r"(?:saldo atual|saldo final)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
    },
    "balancete": _extrair_generico,
    "checklist_documental": _extrair_generico,
    "oficio_encaminhamento": _extrair_generico,
    "relatorio_execucao_objeto": _extrair_generico,
    "folha_pagamento": lambda texto: {
        "competencia": _buscar((r"(?:compet[eê]ncia)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "empregador": _buscar((r"(?:empregador|empresa)\s*[:\-]?\s*(.+)",), texto),
        "total_liquido": _buscar((r"(?:total l[ií]quido|l[ií]quido)\s*[:\-]?\s*(R\$\s*[0-9.,]+|[0-9.,]+)",), texto),
        "quantidade_trabalhadores": _buscar((r"(?:funcion[aá]rios|empregados|trabalhadores)\s*[:\-]?\s*([0-9]+)",), texto),
    },
    "administrativo_sgpe": _extrair_generico,
    "assinaturas_autenticacoes": _extrair_generico,
    "outros_nao_classificados": _extrair_generico,
}
