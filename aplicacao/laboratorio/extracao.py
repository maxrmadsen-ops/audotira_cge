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


def _nome_trabalhador(texto: str) -> str:
    # Holerite escaneado: cabeçalho "Nome do Funcionário" e linha seguinte com o nome.
    apos_rotulo = re.search(
        r"nome\s+do\s+funcion[aá]rio[^\n]{0,100}\n\s*(?:\d+\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç .']{6,70})",
        texto or "",
        flags=re.IGNORECASE,
    )
    if apos_rotulo:
        candidato = re.sub(r"\s+", " ", apos_rotulo.group(1)).strip(" :-|")
        if len(candidato.split()) >= 2 and "APAE" not in candidato.upper():
            return candidato
    padroes = (
        r"(?:nome\s+do\s+empregado|nome\s+do\s+funcion[aá]rio|funcion[aá]rio|empregado|trabalhador)\s*[:\-]?\s*([A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç .']{6,90})",
        r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}){2,5})\b",
    )
    bloqueados = {
        "BANCO DO BRASIL",
        "COMPROVANTE DE",
        "TOTAL DE",
        "DEPARTAMENTO",
        "SEGUNDA VIA",
        "ASSOCIACAO",
        "ASSOCIAÇÃO",
        "RECIBO DE PAGAMENTO",
        "DEMONSTRATIVO DE",
        "APAE MRD",
        "APAE ASSOC",
        "MARIA ROSALINA",
    }
    for padrao in padroes:
        for achado in re.finditer(padrao, texto or ""):
            nome = re.sub(r"\s+", " ", achado.group(1)).strip(" :-|")
            if any(bloco in nome.upper() for bloco in bloqueados):
                continue
            if len(nome.split()) >= 2 and not re.search(r"\d", nome):
                return nome
    return ""


def _moeda_no_contexto(texto: str, rotulos: tuple[str, ...]) -> str:
    for rotulo in rotulos:
        achado = re.search(
            rf"{rotulo}\s*[:\-]?\s*(R\$\s*)?([0-9]{{1,3}}(?:\.[0-9]{{3}})*,[0-9]{{2}}|[0-9]+,[0-9]{{2}})",
            texto or "",
            flags=re.IGNORECASE,
        )
        if achado:
            return (achado.group(0).split(":")[-1] if ":" in achado.group(0) else achado.group(2)).strip()
        # valor na mesma linha ou na seguinte
        achado = re.search(
            rf"{rotulo}[^\n]{{0,40}}?(R\$\s*[0-9.,]+|[0-9]{{1,3}}(?:\.[0-9]{{3}})*,[0-9]{{2}})",
            texto or "",
            flags=re.IGNORECASE,
        )
        if achado:
            return achado.group(1).strip()
    return ""


def _extrair_holerite(texto: str) -> dict[str, str]:
    funcionario = _nome_trabalhador(texto)
    cargo = _buscar(
        (
            rf"{re.escape(funcionario.split()[0]) if funcionario else 'FUNCIONARIO'}[^\n]{{0,40}}\n\s*([A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]{{3,40}})\s+Data\s+Admiss",
            r"(?:cargo|fun[cç][aã]o)\s*[:\-]?\s*(?!presidente)([^\n]{3,60})",
            r"\b(Professor|Professora|Assistente|Auxiliar|Coordenador[a]?|Cuidador[a]?)\b",
        ),
        texto,
    )
    if cargo.lower().startswith("presidente"):
        cargo = _buscar((r"\b(Professor|Professora|Assistente|Auxiliar|Coordenador[a]?|Cuidador[a]?)\b",), texto)
    return {
        "empregador": _buscar(
            (
                r"(APAE\s+ASSOC\.?[^\n]{0,40})",
                r"(?:empregador|empresa|raz[aã]o social)\s*[:\-]?\s*([^\n]{3,80})",
            ),
            texto,
        ),
        "funcionario": funcionario,
        "identificadores": _buscar(
            (
                r"(?:matr[ií]cula|pis)\s*[:\-]?\s*([0-9.\-/]+)",
                r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b",
            ),
            texto,
        ),
        "cargo": cargo,
        "competencia": _buscar(
            (
                r"(?:compet[eê]ncia|refer[eê]ncia|m[eê]s/?ano|per[ií]odo)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{2,4})",
                r"\b((?:0?[1-9]|1[0-2])[/.\-]20[0-9]{2})\s+Mensal\b",
                r"\b((?:0?[1-9]|1[0-2])[/.\-]20[0-9]{2})\b",
            ),
            texto,
        ),
        "data_admissao": _buscar((r"(?:admiss[aã]o|data de admiss[aã]o)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",), texto),
        "salario_base": _moeda_no_contexto(texto, ("sal[aá]rio[\\s\\-]?base",)),
        "total_proventos": _buscar((r"Total\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s+[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}",), texto)
        or _moeda_no_contexto(texto, ("total\\s+de\\s+proventos", "proventos")),
        "total_descontos": _buscar((r"Total\s+[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",), texto)
        or _moeda_no_contexto(texto, ("total\\s+de\\s+descontos", "descontos")),
        "valor_liquido": _moeda_no_contexto(texto, ("total\\s+l[ií]quido", "l[ií]quido\\s+a\\s+receber", "valor\\s+l[ií]quido", "l[ií]quido")),
        "irrf": _moeda_no_contexto(texto, ("irrf", "i\\.?r\\.?r\\.?f\\.?")),
        "inss": _moeda_no_contexto(texto, ("inss",)),
        "rubricas_proventos": _listar_rubricas(texto, "provento"),
        "rubricas_descontos": _listar_rubricas(texto, "desconto"),
        "bases_calculo": "",
        "assinaturas": _buscar((r"(assinatura|carimbo|atesto).{0,40}",), texto),
        "liquido_calculado": "",
    }


def _listar_rubricas(texto: str, tipo: str) -> str:
    """Coleta linhas candidatas a rubrica; vazio se não houver evidência tabular."""
    linhas = []
    for linha in (texto or "").splitlines():
        limpa = linha.strip()
        if not limpa:
            continue
        if re.search(r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}", limpa) and len(limpa) > 8:
            if tipo == "desconto" and re.search(r"inss|irrf|desconto|faltas|vale", limpa, re.I):
                linhas.append(limpa[:120])
            elif tipo == "provento" and re.search(r"sal[aá]rio|hora|adicional|provento|vencimento", limpa, re.I):
                linhas.append(limpa[:120])
        if len(linhas) >= 8:
            break
    return " | ".join(linhas)


def _extrair_comprovante(texto: str) -> dict[str, str]:
    return {
        "instituicao": _buscar((r"(banco\s+do\s+brasil|caixa econ[oô]mica|sicredi|sicoob|bradesco|ita[uú]|banco\s+[^\n]{2,40})",), texto),
        "titular_origem": _buscar((r"(?:titular|nome do pagador|cliente)\s*[:\-]?\s*([^\n]{3,80})",), texto),
        "conta_origem": _buscar((r"(?:agencia|ag[eê]ncia)\s*[:\-]?\s*([0-9.\-]+).{0,40}conta\s*[:\-]?\s*([0-9.\-X]+)", r"conta\s*[:\-]?\s*([0-9.\-X]+)"), texto),
        "beneficiario": _buscar(
            (
                r"(?:transferido para|creditado para)[\s\S]{0,120}?cliente\s*[:\-]?\s*([^\n]{3,80})",
                r"(?:favorecido|benefici[aá]rio|destinat[aá]rio|creditado)\s*[:\-]?\s*([^\n]{3,80})",
            ),
            texto,
        ),
        "dados_destino": _buscar(
            (
                r"(?:transferido para)[\s\S]{0,160}?ag[eê]ncia\s*[:\-]?\s*([0-9.\-]+\s*conta\s*[:\-]?\s*[0-9.\-X]+)",
                r"(?:conta destino|destino|conta creditada)\s*[:\-]?\s*([^\n]{3,80})",
            ),
            texto,
        ),
        "data_hora": _buscar(
            (
                r"(?:data da transfer[eê]ncia)\s*[:\-]?\s*([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})",
                r"([0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4}(?:\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)?)",
            ),
            texto,
        ),
        "valor": _moeda_no_contexto(texto, ("valor total", "valor da transfer[eê]ncia", "valor pago", "valor")),
        "tipo_operacao": _buscar((r"(ted|doc|pix|transfer[eê]ncia)",), texto),
        "identificadores": _buscar(
            (
                r"(?:nr\.?\s*documento|nr\.?\s*docum)\s*[:\-]?\s*([0-9.\-]+)",
                r"(?:autentica[cç][aã]o|nsu|protocolo)\s*[:\-]?\s*([A-Za-z0-9\-./]+)",
            ),
            texto,
        ),
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
