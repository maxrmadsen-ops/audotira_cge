"""Conciliação sugerida. Coincidência de valor não comprova pagamento."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from aplicacao.laboratorio.escolhas import EstadoVinculo
from aplicacao.laboratorio.models import CadeiaConciliacao, RegiaoDocumental


def _dinheiro(texto: str) -> Decimal | None:
    bruto = (texto or "").strip().replace("R$", "").strip()
    if not bruto:
        return None
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        return Decimal(bruto)
    except (InvalidOperation, ValueError):
        return None


def _moeda(valor: Decimal | None) -> str:
    if valor is None:
        return "não extraído"
    quantizado = f"{valor.quantize(Decimal('0.01')):.2f}"
    inteiro, frac = quantizado.split(".")
    grupos = []
    while inteiro:
        grupos.append(inteiro[-3:])
        inteiro = inteiro[:-3]
    return ".".join(reversed(grupos)) + "," + frac


def _campo(regiao: RegiaoDocumental, chave: str):
    return next((item for item in regiao.campos.all() if item.chave == chave), None)


def _texto(regiao: RegiaoDocumental, chave: str) -> str:
    campo = _campo(regiao, chave)
    if campo is None:
        return ""
    return (campo.valor_original or campo.valor_normalizado or "").strip()


def _valor(regiao: RegiaoDocumental, chave: str) -> Decimal | None:
    campo = _campo(regiao, chave)
    if campo is None:
        return None
    return _dinheiro(campo.valor_normalizado or campo.valor_original)


def _evidencia(regiao: RegiaoDocumental, chave: str, rotulo: str) -> dict:
    campo = _campo(regiao, chave)
    return {
        "rotulo": rotulo,
        "valor": (campo.valor_original if campo else "") or "não extraído",
        "pagina": regiao.pagina.numero_fisico,
        "peca": regiao.pk,
        "chave": chave,
    }


def _nome_proximo(esquerda: str, direita: str) -> bool:
    a = " ".join((esquerda or "").upper().split())
    b = " ".join((direita or "").upper().split())
    if len(a) < 5 or len(b) < 5:
        return False
    return a in b or b in a


def _situacao_numeros(esperado: Decimal | None, obtido: Decimal | None) -> str:
    if esperado is None or obtido is None:
        return "nao_verificavel"
    return "confere" if esperado == obtido else "diverge"


def verificar_folha(holerite: RegiaoDocumental, transferencia: RegiaoDocumental | None) -> list[dict]:
    proventos = _valor(holerite, "total_proventos")
    descontos = _valor(holerite, "total_descontos")
    liquido = _valor(holerite, "valor_liquido")
    calculado = proventos - descontos if proventos is not None and descontos is not None else None
    transferido = _valor(transferencia, "valor") if transferencia is not None else None
    competencia = _texto(holerite, "competencia")
    pagamento = _texto(transferencia, "data_hora") if transferencia is not None else ""
    trabalhador = _texto(holerite, "funcionario")
    beneficiario = _texto(transferencia, "beneficiario") if transferencia is not None else ""
    rubricas_proventos = _soma_rubricas(holerite, "provento")
    rubricas_descontos = _soma_rubricas(holerite, "desconto")
    verificacoes = [
        {
            "codigo": "soma_proventos",
            "titulo": "Soma das rubricas de proventos",
            "situacao": _situacao_numeros(rubricas_proventos, proventos),
            "detalhe": _detalhe_soma("Proventos das rubricas", rubricas_proventos, "Total de proventos", proventos),
            "evidencias": [_evidencia(holerite, "total_proventos", "Total de proventos")],
        },
        {
            "codigo": "soma_descontos",
            "titulo": "Soma das rubricas de descontos",
            "situacao": _situacao_numeros(rubricas_descontos, descontos),
            "detalhe": _detalhe_soma("Descontos das rubricas", rubricas_descontos, "Total de descontos", descontos),
            "evidencias": [_evidencia(holerite, "total_descontos", "Total de descontos")],
        },
        {
            "codigo": "liquido_calculado",
            "titulo": "Líquido calculado",
            "situacao": _situacao_numeros(calculado, liquido),
            "detalhe": (
                f"{_moeda(proventos)} − {_moeda(descontos)} = {_moeda(calculado)}. "
                f"Líquido informado: {_moeda(liquido)}."
            ),
            "evidencias": [
                _evidencia(holerite, "total_proventos", "Total de proventos"),
                _evidencia(holerite, "total_descontos", "Total de descontos"),
                _evidencia(holerite, "valor_liquido", "Valor líquido"),
            ],
        },
        {
            "codigo": "liquido_e_transferencia",
            "titulo": "Líquido e valor transferido",
            "situacao": _situacao_numeros(liquido, transferido) if transferencia is not None else "nao_verificavel",
            "detalhe": (
                "Não há comprovante associado nesta cadeia. A ausência nesta amostra não é irregularidade."
                if transferencia is None
                else (
                    f"Líquido {_moeda(liquido)} e transferência {_moeda(transferido)}. "
                    "A coincidência numérica não comprova o pagamento."
                )
            ),
            "evidencias": [
                _evidencia(holerite, "valor_liquido", "Valor líquido"),
                *([_evidencia(transferencia, "valor", "Valor transferido")] if transferencia is not None else []),
            ],
        },
        {
            "codigo": "competencia_e_pagamento",
            "titulo": "Competência e data do pagamento",
            "situacao": "nao_verificavel" if competencia or pagamento else "nao_verificavel",
            "detalhe": (
                f"Competência {competencia or 'não extraída'}; data do pagamento {pagamento or 'não extraída'}. "
                "Datas diferentes não são tratadas como irregularidade."
            ),
            "evidencias": [
                _evidencia(holerite, "competencia", "Competência"),
                *([_evidencia(transferencia, "data_hora", "Data da transferência")] if transferencia is not None else []),
            ],
        },
        {
            "codigo": "beneficiario",
            "titulo": "Correspondência de beneficiário",
            "situacao": "pendente" if _nome_proximo(trabalhador, beneficiario) else "nao_verificavel",
            "detalhe": (
                f"Sugestão: {trabalhador or 'trabalhador não extraído'} e {beneficiario or 'beneficiário não extraído'}. "
                "A semelhança do nome não confirma a identidade."
            ),
            "evidencias": [
                _evidencia(holerite, "funcionario", "Trabalhador"),
                *([_evidencia(transferencia, "beneficiario", "Beneficiário")] if transferencia is not None else []),
            ],
        },
    ]
    return verificacoes


def _detalhe_soma(rotulo_a: str, valor_a: Decimal | None, rotulo_b: str, valor_b: Decimal | None) -> str:
    if valor_a is None:
        return f"{rotulo_a} não verificável com as rubricas extraídas. {rotulo_b}: {_moeda(valor_b)}."
    return f"{rotulo_a} {_moeda(valor_a)}. {rotulo_b} {_moeda(valor_b)}."


def _soma_rubricas(regiao: RegiaoDocumental, natureza: str) -> Decimal | None:
    total = Decimal("0")
    achou = False
    for rubrica in regiao.rubricas.all():
        if rubrica.natureza != natureza:
            continue
        valor = _dinheiro(rubrica.valor_normalizado or rubrica.valor_original)
        if valor is None:
            return None
        total += valor
        achou = True
    return total if achou else None


def _separacao(matematica: str, tem_comprovante: bool) -> dict:
    return {
        "vinculo": "sugerido",
        "consistencia_matematica": matematica,
        "comprovacao_documental": "pendente" if tem_comprovante else "nao_verificavel",
        "analise_conformidade": "nao_aplicavel",
        "decisao_administrativa": "pendente",
    }


def _item_por_texto(lote, texto: str):
    plano = lote.prestacao_parceria.planos.order_by("-versao").first()
    if plano is None:
        return None, "Não há plano de trabalho associado a esta prestação."
    itens = list(plano.itens.all())
    total = sum((item.valor_previsto or Decimal("0")) for item in itens)
    escolhido = next((item for item in itens if texto in (item.descricao or "").lower()), None)
    if escolhido is None:
        return None, (
            f"Nenhum item do plano menciona «{texto}». "
            f"O total previsto do plano é {_moeda(total)} e não é despesa executada."
        )
    return escolhido, (
        f"Sugestão pela descrição do item, não pelo valor. "
        f"O item prevê {_moeda(escolhido.valor_previsto)}; o plano soma {_moeda(total)}. "
        "Esse orçamento não é o valor desta parcela e a diferença não é divergência da despesa."
    )


def _cadeias_folha(lote, regioes: list[RegiaoDocumental]) -> list[dict]:
    holerites = [regiao for regiao in regioes if regiao.tipo_documental == "holerite"]
    transferencias = [regiao for regiao in regioes if regiao.tipo_documental == "comprovante_transferencia"]
    item, criterio = _item_por_texto(lote, "profissionais")
    if item is None:
        item, criterio = _item_por_texto(lote, "pessoal")
    propostas = []
    for holerite in holerites:
        liquido = _valor(holerite, "valor_liquido")
        trabalhador = _texto(holerite, "funcionario")
        candidatas = []
        for transferencia in transferencias:
            valor = _valor(transferencia, "valor")
            if liquido is None or valor is None or liquido != valor:
                continue
            nome = _nome_proximo(trabalhador, _texto(transferencia, "beneficiario"))
            mesma = holerite.pagina_id == transferencia.pagina_id
            if nome or mesma:
                candidatas.append((0 if mesma else 1, transferencia))
        candidatas.sort(key=lambda item_ord: item_ord[0])
        transferencia = candidatas[0][1] if candidatas else None
        verificacoes = verificar_folha(holerite, transferencia)
        matematica = next(item_v["situacao"] for item_v in verificacoes if item_v["codigo"] == "liquido_calculado")
        verificacoes.append(
            {
                "codigo": "plano_trabalho",
                "titulo": "Item previsto no plano",
                "situacao": "nao_verificavel",
                "detalhe": criterio,
                "evidencias": [_evidencia(holerite, "valor_liquido", "Parcela identificada")],
            }
        )
        propostas.append(
            {
                "codigo": f"folha-{holerite.pk}",
                "titulo": f"Folha · {trabalhador or 'trabalhador não extraído'} · página {holerite.pagina.numero_fisico}",
                "item_plano": item,
                "criterio_item": criterio,
                "execucao": holerite,
                "comprovante": transferencia,
                "apoio": None,
                "verificacoes": verificacoes,
                "separacao": _separacao(matematica, transferencia is not None),
                "confianca": "sugerida",
            }
        )
    return propostas


def comparar_datas_evento(data_a: str, origem_a: str, data_b: str, origem_b: str) -> dict:
    """Compara o mesmo evento em dois documentos. Não autentica nenhum deles."""
    from aplicacao.laboratorio.validacao import normalizar_data

    esquerda = normalizar_data(data_a) or (data_a or "").strip()
    direita = normalizar_data(data_b) or (data_b or "").strip()
    if not esquerda or not direita:
        return {
            "situacao": "nao_verificavel",
            "detalhe": (
                f"{origem_a or 'Primeiro documento'}: {esquerda or 'não lida'}. "
                f"{origem_b or 'Segundo documento'}: {direita or 'não lida'}. "
                "A comparação não foi fechada e nenhum documento foi autenticado."
            ),
        }
    if esquerda == direita:
        return {
            "situacao": "coincidente",
            "detalhe": (
                f"{origem_a}: {esquerda}. {origem_b}: {direita}. "
                "As evidências permanecem independentes. A coincidência não autentica os documentos nem comprova quitação."
            ),
        }
    return {
        "situacao": "diverge",
        "detalhe": (
            f"{origem_a}: {esquerda}. {origem_b}: {direita}. "
            "As datas divergem. Nenhuma das duas foi confirmada."
        ),
    }


def _verificacao_datas_desligamento(rescisao: RegiaoDocumental, apoio: RegiaoDocumental | None) -> dict:
    data_rescisao = _texto(rescisao, "data_desligamento")
    data_apoio = ""
    chave_apoio = "data_afastamento"
    if apoio is not None:
        data_apoio = _texto(apoio, "data_afastamento") or _texto(apoio, "data_desligamento")
        if not _texto(apoio, "data_afastamento") and _texto(apoio, "data_desligamento"):
            chave_apoio = "data_desligamento"
    origem_a = f"Rescisão · página {rescisao.pagina.numero_fisico} · Data de desligamento"
    origem_b = (
        f"Quitação · página {apoio.pagina.numero_fisico} · Data de Afastamento"
        if apoio is not None
        else "Quitação"
    )
    comparado = comparar_datas_evento(data_rescisao, origem_a, data_apoio, origem_b)
    evidencias = [_evidencia(rescisao, "data_desligamento", "Data de desligamento")]
    if apoio is not None:
        evidencias.append(_evidencia(apoio, chave_apoio, "Data de Afastamento"))
    return {
        "codigo": "datas_desligamento",
        "titulo": "Data de desligamento e de afastamento",
        "situacao": comparado["situacao"],
        "detalhe": comparado["detalhe"],
        "evidencias": evidencias,
    }


def _cadeias_rescisao(lote, regioes: list[RegiaoDocumental]) -> list[dict]:
    rescisoes = [regiao for regiao in regioes if regiao.tipo_documental == "termo_rescisao"]
    quitacoes = [regiao for regiao in regioes if regiao.tipo_documental == "termo_quitacao"]
    transferencias = [regiao for regiao in regioes if regiao.tipo_documental == "comprovante_transferencia"]
    item, criterio = _item_por_texto(lote, "rescis")
    propostas = []
    for rescisao in rescisoes:
        trabalhador = _texto(rescisao, "trabalhador")
        apoio = next(
            (
                quitacao
                for quitacao in quitacoes
                if _nome_proximo(trabalhador, _texto(quitacao, "trabalhador"))
                or abs(quitacao.pagina.numero_fisico - rescisao.pagina.numero_fisico) <= 1
            ),
            None,
        )
        liquido = _valor(rescisao, "total_liquido")
        bruto = _valor(rescisao, "total_bruto")
        deducoes = _valor(rescisao, "deducoes")
        calculado = _valor(rescisao, "liquido_calculado")
        if calculado is None and bruto is not None and deducoes is not None:
            calculado = bruto - deducoes
        referencia = liquido if liquido is not None else calculado
        comprovante = None
        origem_valor = ""
        proxima_diferente = ""
        for transferencia in transferencias:
            valor = _valor(transferencia, "valor")
            mesmo_nome = _nome_proximo(trabalhador, _texto(transferencia, "beneficiario"))
            mesma_faixa = abs(transferencia.pagina.numero_fisico - rescisao.pagina.numero_fisico) <= 2
            if referencia is not None and valor is not None and referencia == valor and mesmo_nome and mesma_faixa:
                comprovante = transferencia
                origem_valor = "lido" if liquido is not None and liquido == valor else "calculado"
                break
            if not proxima_diferente and mesmo_nome and mesma_faixa:
                proxima_diferente = (
                    f" Há transferência na página {transferencia.pagina.numero_fisico} "
                    f"com nome semelhante e valor {_moeda(valor)}. Não foi vinculada."
                )
        if bruto is not None and deducoes is not None and calculado is not None and calculado == bruto - deducoes:
            situacao_calculo = "confere"
            detalhe_calculo = (
                f"{_moeda(bruto)} − {_moeda(deducoes)} = {_moeda(calculado)}. "
                "Este é o líquido calculado, distinto do valor lido no campo."
            )
        else:
            situacao_calculo = "nao_verificavel"
            detalhe_calculo = "Bruto ou deduções não estão ambos legíveis, então o líquido não foi calculado."
        if liquido is None:
            situacao_lido = "nao_verificavel"
            detalhe_lido = "O campo VALOR LÍQUIDO não teve leitura pontuada confiável e permanece pendente."
        elif calculado is not None and liquido == calculado:
            situacao_lido = "confere"
            detalhe_lido = (
                f"Líquido lido no recorte {_moeda(liquido)}. Coincide com o calculado. "
                "A leitura continua pendente de revisão humana."
            )
        elif calculado is not None:
            situacao_lido = "diverge"
            detalhe_lido = f"Líquido lido {_moeda(liquido)} e líquido calculado {_moeda(calculado)} divergem. Nenhum dos dois foi confirmado."
        else:
            situacao_lido = "pendente"
            detalhe_lido = f"Líquido lido no recorte {_moeda(liquido)}. Sem cálculo para comparar."
        data_rescisao = _texto(rescisao, "data_desligamento")
        data_transferencia = _texto(comprovante, "data_hora") if comprovante is not None else ""
        contexto_data = ""
        if data_rescisao and data_transferencia:
            if data_rescisao in data_transferencia or data_transferencia.startswith(data_rescisao):
                contexto_data = f" A data de afastamento lida {data_rescisao} e a data da transferência {data_transferencia} coincidem como contexto, sem provar o pagamento."
            else:
                contexto_data = (
                    f" Afastamento lido {data_rescisao}; transferência {data_transferencia}. "
                    "Datas diferentes não são tratadas como irregularidade."
                )
        detalhe_pagamento = (
            (
                f"Candidato: transferência da página {comprovante.pagina.numero_fisico} no valor {_moeda(_valor(comprovante, 'valor'))}. "
                f"A comparação usou o líquido {origem_valor} {_moeda(referencia)}. "
                "A coincidência matemática não comprova o pagamento. "
                "A semelhança do nome é correspondência sugerida, não identidade confirmada. "
                "A data da transferência não substitui a data da comunicação."
                + contexto_data
            )
            if comprovante is not None
            else (
                "Nenhum comprovante com o mesmo valor da rescisão foi associado. "
                "Semelhança de nome com outra transferência, inclusive a da página 17, não cria esse vínculo. "
                "A ausência nesta amostra não é irregularidade."
                + proxima_diferente
            )
        )
        verificacoes = [
            _verificacao_datas_desligamento(rescisao, apoio),
            {
                "codigo": "liquido_calculado",
                "titulo": "Líquido calculado",
                "situacao": situacao_calculo,
                "detalhe": detalhe_calculo,
                "evidencias": [
                    _evidencia(rescisao, "total_bruto", "Total bruto"),
                    _evidencia(rescisao, "deducoes", "Deduções"),
                    _evidencia(rescisao, "liquido_calculado", "Líquido calculado"),
                ],
            },
            {
                "codigo": "liquido_lido",
                "titulo": "Líquido lido",
                "situacao": situacao_lido,
                "detalhe": detalhe_lido,
                "evidencias": [_evidencia(rescisao, "total_liquido", "Total líquido lido")],
            },
            {
                "codigo": "pagamento_rescisao",
                "titulo": "Comprovante da rescisão",
                "situacao": "pendente" if comprovante is not None else "nao_verificavel",
                "detalhe": detalhe_pagamento,
                "evidencias": [
                    _evidencia(rescisao, "total_liquido", "Total líquido lido"),
                    _evidencia(rescisao, "liquido_calculado", "Líquido calculado"),
                ]
                + ([_evidencia(comprovante, "valor", "Valor transferido")] if comprovante is not None else []),
            },
            {
                "codigo": "plano_trabalho",
                "titulo": "Item previsto no plano",
                "situacao": "nao_verificavel",
                "detalhe": criterio,
                "evidencias": [],
            },
        ]
        propostas.append(
            {
                "codigo": f"rescisao-{rescisao.pk}",
                "titulo": f"Rescisão · {trabalhador or 'trabalhador não extraído'} · página {rescisao.pagina.numero_fisico}",
                "item_plano": item,
                "criterio_item": criterio,
                "execucao": rescisao,
                "comprovante": comprovante,
                "apoio": apoio,
                "verificacoes": verificacoes,
                "separacao": _separacao(situacao_calculo, comprovante is not None),
                "confianca": "sugerida",
            }
        )
    return propostas


def painel_da_cadeia(cadeia) -> dict:
    conferencias = []
    pendencias = []
    for item in cadeia.verificacoes or []:
        if item.get("situacao") in {"confere", "coincidente"}:
            conferencias.append(item.get("titulo") or "")
        else:
            pendencias.append(item.get("titulo") or "")
    if cadeia.comprovante_id and cadeia.comprovante is not None:
        comprovado = (
            f"{cadeia.comprovante.tipo_documental} · página {cadeia.comprovante.pagina.numero_fisico}. "
            "Sugestão de vínculo. A coincidência não comprova pagamento."
        )
    else:
        comprovado = "Sem comprovante associado. Isso não indica irregularidade."
    if cadeia.execucao_id and cadeia.execucao is not None:
        executado = f"{cadeia.execucao.tipo_documental} · página {cadeia.execucao.pagina.numero_fisico}"
    else:
        executado = "Documento de execução não associado"
    if cadeia.estado == EstadoVinculo.CONFIRMADO:
        proxima = "Vínculo confirmado pelo auditor. A despesa segue sem aprovação automática."
    elif cadeia.estado == EstadoVinculo.REJEITADO:
        proxima = "Vínculo rejeitado. A decisão administrativa continua pendente."
    else:
        proxima = "Conferir os recortes e confirmar, corrigir ou rejeitar o vínculo."
    return {
        "previsto": cadeia.criterio_item or "Item do plano não sugerido",
        "executado": executado,
        "comprovado": comprovado,
        "conferencias": conferencias or ["Nenhuma conferência fechou com os dados lidos"],
        "pendencias": pendencias or ["Nenhuma pendência registrada"],
        "proxima": proxima,
    }


def _cadeias_fgts(lote, regioes: list[RegiaoDocumental]) -> list[dict]:
    guias = [regiao for regiao in regioes if regiao.tipo_documental == "guia_fgts"]
    comprovantes = [
        regiao
        for regiao in regioes
        if regiao.tipo_documental in {"comprovante_fgts", "comprovante_transferencia"}
    ]
    item, criterio = _item_por_texto(lote, "fgts")
    propostas = []
    for guia in guias:
        valor = _valor(guia, "valor_recolhimento")
        comprovante = None
        for candidato in comprovantes:
            if candidato.pk == guia.pk:
                continue
            outro = _valor(candidato, "valor") or _valor(candidato, "valor_recolhimento")
            if valor is None or outro is None or valor != outro:
                continue
            if abs(candidato.pagina.numero_fisico - guia.pagina.numero_fisico) <= 2:
                comprovante = candidato
                break
        deposito, total_guia = _valores_na_guia(guia.texto_regiao or "")
        if deposito is None or total_guia is None:
            situacao_peca = "nao_verificavel"
            detalhe_peca = "Depósito e total a recolher não estão ambos legíveis na mesma peça."
        elif deposito == total_guia:
            situacao_peca = "confere"
            detalhe_peca = (
                f"Depósito {_moeda(deposito)} e total a recolher {_moeda(total_guia)} aparecem na mesma peça. "
                "O comprovante não foi separado da guia. A coincidência interna não comprova o recolhimento "
                "e não liga esta guia à transferência da página 17."
            )
        else:
            situacao_peca = "diverge"
            detalhe_peca = (
                f"Depósito {_moeda(deposito)} e total a recolher {_moeda(total_guia)} divergem na mesma peça. "
                "Isso não conclui irregularidade nem pagamento."
            )
        data_pagamento = _texto(guia, "data_pagamento")
        vencimento = _texto(guia, "vencimento")
        verificacoes = [
            {
                "codigo": "valores_na_mesma_peca",
                "titulo": "Depósito e total na mesma peça",
                "situacao": situacao_peca,
                "detalhe": detalhe_peca,
                "evidencias": [_evidencia(guia, "valor_recolhimento", "Valor de recolhimento")],
            },
            {
                "codigo": "recolhimento_fgts",
                "titulo": "Guia e comprovante de FGTS",
                "situacao": "pendente" if comprovante is not None else "nao_verificavel",
                "detalhe": (
                    f"Valor da guia {_moeda(valor)} coincide com um comprovante próximo. "
                    "Isso não comprova o recolhimento nem o vincula à transferência salarial."
                    if comprovante is not None
                    else (
                        f"Valor da guia {_moeda(valor)}. Não há comprovante próximo com o mesmo valor. "
                        "A ausência nesta amostra não é irregularidade e não liga esta guia à página 17."
                    )
                ),
                "evidencias": [_evidencia(guia, "valor_recolhimento", "Valor de recolhimento")],
            },
            {
                "codigo": "data_e_vencimento",
                "titulo": "Data lida e vencimento",
                "situacao": "nao_verificavel",
                "detalhe": (
                    f"Data de pagamento lida: {data_pagamento or 'não extraída'}. "
                    f"Vencimento: {vencimento or 'não extraído'}. "
                    "Datas diferentes não são tratadas como irregularidade."
                ),
                "evidencias": [_evidencia(guia, "data_pagamento", "Data de pagamento")],
            },
            {
                "codigo": "plano_trabalho",
                "titulo": "Item previsto no plano",
                "situacao": "nao_verificavel",
                "detalhe": criterio,
                "evidencias": [],
            },
        ]
        propostas.append(
            {
                "codigo": f"fgts-{guia.pk}",
                "titulo": f"FGTS · página {guia.pagina.numero_fisico} · {_texto(guia, 'competencia') or 'competência não extraída'}",
                "item_plano": item,
                "criterio_item": criterio,
                "execucao": guia,
                "comprovante": comprovante,
                "apoio": None,
                "verificacoes": verificacoes,
                "separacao": _separacao(situacao_peca, comprovante is not None),
                "confianca": "sugerida",
            }
        )
    return propostas


def _valores_na_guia(texto: str) -> tuple[Decimal | None, Decimal | None]:
    moeda = r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}"
    deposito = _moeda_rotulo(texto, rf"valor\s+dep[oó]sito\s*[:\-]?\s*({moeda})")
    recibo = _moeda_rotulo(texto, rf"valor\s+total\s*[:\-]?\s*({moeda})")
    coluna = re.search(
        rf"total\s+a\s+recolher.{{0,160}}?{moeda}\s+{moeda}\s+({moeda})",
        texto or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    guia = _dinheiro(coluna.group(1)) if coluna else None
    return deposito, guia if guia is not None else recibo


def _moeda_rotulo(texto: str, padrao: str) -> Decimal | None:
    achado = re.search(padrao, texto or "", flags=re.IGNORECASE)
    if not achado:
        return None
    return _dinheiro(achado.group(1))


def depurar_vinculos_sugeridos(lote) -> None:
    """Remove sugestões que o critério novo não sustentaria. Não mexe em decisão humana."""
    from aplicacao.laboratorio.models import VinculoEvidencia

    for vinculo in VinculoEvidencia.objects.filter(lote=lote, estado=EstadoVinculo.SUGERIDO):
        criterios = vinculo.criterios or []
        if vinculo.tipo_vinculo == "holerite_transferencia" and "mesmo_valor_liquido" not in criterios:
            vinculo.delete()
        elif vinculo.tipo_vinculo == "rescisao_pagamento" and "mesmo_valor" not in criterios and "valor_calculado" not in criterios:
            vinculo.delete()


def sincronizar_cadeias(lote) -> list[CadeiaConciliacao]:
    depurar_vinculos_sugeridos(lote)
    regioes = list(
        RegiaoDocumental.objects.filter(lote=lote)
        .select_related("pagina")
        .prefetch_related("campos", "rubricas")
    )
    propostas = []
    propostas.extend(_cadeias_folha(lote, regioes))
    propostas.extend(_cadeias_rescisao(lote, regioes))
    propostas.extend(_cadeias_fgts(lote, regioes))
    codigos = {proposta["codigo"] for proposta in propostas}
    existentes = {cadeia.codigo: cadeia for cadeia in lote.cadeias.all()}
    gravadas = []
    for proposta in propostas:
        atual = existentes.get(proposta["codigo"])
        if atual is not None and atual.estado != EstadoVinculo.SUGERIDO:
            gravadas.append(atual)
            continue
        if atual is None:
            atual = CadeiaConciliacao(lote=lote, estado=EstadoVinculo.SUGERIDO)
        for campo, valor in proposta.items():
            setattr(atual, campo, valor)
        atual.save()
        gravadas.append(atual)
    lote.cadeias.filter(estado=EstadoVinculo.SUGERIDO).exclude(codigo__in=codigos).delete()
    return gravadas
