"""Conferência integrada somente leitura. Não grava cadeias nem confirma pagamento."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aplicacao.laboratorio.apresentacao import eh_placeholder
from aplicacao.laboratorio.catalogo import rotulo_tipo
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoVinculo
from aplicacao.laboratorio.extracao import texto_moeda

CENTAVO = Decimal("0.01")
_NAO_SOMA = {"ambiguo", "inconsistente"}
_CHAVES_OBRIGACAO = {
    "holerite": "valor_liquido",
    "folha_pagamento": "valor_liquido",
    "termo_rescisao": "total_liquido",
    "guia_fgts": "valor_recolhimento",
}
_SITUACOES = {
    "sem_execucao": "Sem execução identificada nesta amostra",
    "sugerida": "Correspondência documental sugerida",
    "confirmada": "Correspondência confirmada pelo auditor",
    "sem_comprovante": "Documento de execução sem comprovante",
    "divergencia": "Divergência de valor",
    "insuficiente": "Informação insuficiente",
    "rejeitada": "Vínculo rejeitado pelo auditor",
}


def _decimal(texto: str) -> Decimal | None:
    bruto = (texto or "").strip().replace("R$", "").strip()
    if not bruto:
        return None
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        return Decimal(bruto).quantize(CENTAVO)
    except (InvalidOperation, ValueError):
        return None


def _campo(regiao, chave: str):
    if regiao is None:
        return None
    return next((campo for campo in regiao.campos.all() if campo.chave == chave), None)


def _leitura(regiao, chave: str) -> tuple[Decimal | None, bool, str]:
    campo = _campo(regiao, chave)
    if campo is None:
        return None, False, ""
    ambiguo = (campo.estado_confianca or "") in _NAO_SOMA
    return _decimal(campo.valor_normalizado or campo.valor_original), ambiguo, campo.valor_original or ""


def _moeda(valor: Decimal | None) -> str:
    if valor is None:
        return "não extraído"
    return texto_moeda(valor.quantize(CENTAVO))


def _papel_comprovante(estado: str) -> str:
    if estado == EstadoVinculo.CONFIRMADO:
        return "Comprovante confirmado"
    if estado == EstadoVinculo.REJEITADO:
        return "Comprovante de vínculo rejeitado"
    return "Comprovante sugerido"


def _situacao(codigos: set[str], tem_documento: bool) -> str:
    if not tem_documento:
        return "sem_execucao"
    for codigo in ("divergencia", "insuficiente", "sem_comprovante", "sugerida", "confirmada", "rejeitada"):
        if codigo in codigos:
            return codigo
    return "insuficiente"


_CHAVES_FINANCEIRAS = {
    "valor",
    "valor_liquido",
    "valor_recolhimento",
    "total_liquido",
    "total_proventos",
    "total_descontos",
    "totais",
    "base_recolhimento",
    "saldo_inicial",
    "saldo_final",
}


def montar_cobertura(lote) -> dict:
    """Conta o que já foi lido. Não é percentual de execução do plano."""
    regioes = list(lote.regioes.prefetch_related("campos"))
    efetivas = sum(1 for regiao in regioes if not eh_placeholder(regiao))
    com_campo = 0
    com_valor = 0
    pendentes = 0
    for regiao in regioes:
        campos = list(regiao.campos.all())
        if any((campo.valor_original or "").strip() for campo in campos):
            com_campo += 1
        if any(campo.chave in _CHAVES_FINANCEIRAS and (campo.valor_original or "").strip() for campo in campos):
            com_valor += 1
        if regiao.estado_revisao == "pendente" or any(campo.estado_revisao == EstadoCampo.PENDENTE for campo in campos):
            pendentes += 1
    vinculadas = set()
    for cadeia in lote.cadeias.all():
        if not cadeia.item_plano_id:
            continue
        for identificador in (cadeia.execucao_id, cadeia.apoio_id, cadeia.comprovante_id):
            if identificador:
                vinculadas.add(identificador)
    sem_ocr = lote.paginas.filter(tecnica_utilizada="nativo", quantidade_caracteres__lte=40).count()
    return {
        "pecas": len(regioes),
        "pecas_efetivas": efetivas,
        "pecas_placeholder": len(regioes) - efetivas,
        "paginas_com_peca": lote.regioes.values("pagina_id").distinct().count(),
        "com_campo": com_campo,
        "com_valor": com_valor,
        "vinculadas": len(vinculadas),
        "vinculos_sugeridos": lote.vinculos.filter(estado=EstadoVinculo.SUGERIDO).count(),
        "vinculos_confirmados": lote.vinculos.filter(estado=EstadoVinculo.CONFIRMADO).count(),
        "pendentes": pendentes,
        "sem_ocr": sem_ocr,
        "paginas": lote.quantidade_paginas,
    }


def _nota_guia(regiao, cadeia) -> str:
    texto = (regiao.texto_regiao or "").lower()
    banco = "comprovante de pagamento" in texto or "autenticacao sisbb" in texto or "autenticação sisbb" in texto
    autenticacao = _campo(regiao, "autenticacao")
    ambigua = (
        autenticacao is None
        or (autenticacao.estado_confianca or "") in _NAO_SOMA
        or not (autenticacao.valor_original or "").strip()
    )
    partes = ["Guia e obrigação identificadas."]
    if banco:
        partes.append("Comprovante bancário localizado na mesma peça, sem segundo comprovante.")
    if ambigua:
        partes.append("Autenticação ambígua e pendente de revisão.")
    else:
        partes.append("Autenticação lida e ainda sem confirmação humana.")
    if cadeia.estado != EstadoVinculo.CONFIRMADO:
        partes.append("Recolhimento pendente de confirmação do auditor. O valor não foi somado de novo.")
    return " ".join(partes)


def _explicacao(codigo: str) -> str:
    textos = {
        "sem_execucao": (
            "Nenhum documento de execução desta amostra foi vinculado a esta rubrica. "
            "Isso não indica irregularidade."
        ),
        "sugerida": (
            "Há correspondência documental sugerida. Ela não comprova pagamento nem aprova a despesa. "
            "O documento identificado não representa a execução total da rubrica na vigência."
        ),
        "confirmada": (
            "O auditor confirmou o vínculo. A confirmação não aprova a despesa e não equivale o documento ao orçamento anual."
        ),
        "sem_comprovante": (
            "Há documento de execução e nenhum comprovante vinculado. "
            "A comprovação financeira permanece pendente. Isso não indica irregularidade."
        ),
        "divergencia": (
            "Os valores lidos nos documentos desta rubrica divergem. "
            "A divergência não foi classificada como irregularidade."
        ),
        "insuficiente": "Falta valor legível ou a leitura está ambígua. Esse valor não entrou na soma.",
        "rejeitada": "O auditor rejeitou o vínculo. Os documentos continuam disponíveis para nova análise.",
    }
    return textos[codigo]


def montar_conferencia_integrada(lote) -> dict:
    plano = lote.prestacao_parceria.planos.order_by("-versao", "-id").first()
    itens = list(plano.itens.all().order_by("ordem", "id")) if plano is not None else []
    cadeias = list(
        lote.cadeias.select_related(
            "item_plano",
            "execucao__pagina",
            "comprovante__pagina",
            "apoio__pagina",
        ).prefetch_related("execucao__campos", "comprovante__campos", "apoio__campos")
    )
    por_item: dict[int, list] = {}
    sem_item = []
    for cadeia in cadeias:
        if cadeia.item_plano_id:
            por_item.setdefault(cadeia.item_plano_id, []).append(cadeia)
        else:
            sem_item.append(cadeia)
    somados_obrigacao: set[int] = set()
    somados_sugerido: set[int] = set()
    somados_confirmado: set[int] = set()
    total_executado = Decimal("0.00")
    total_sugerido = Decimal("0.00")
    total_confirmado = Decimal("0.00")
    linhas = []
    for item in itens:
        linha, executado, sugerido, confirmado = _linha_do_item(
            item,
            por_item.get(item.id, []),
            somados_obrigacao,
            somados_sugerido,
            somados_confirmado,
        )
        total_executado += executado
        total_sugerido += sugerido
        total_confirmado += confirmado
        linhas.append(linha)
    if sem_item:
        linha, executado, sugerido, confirmado = _linha_do_item(
            None,
            sem_item,
            somados_obrigacao,
            somados_sugerido,
            somados_confirmado,
        )
        total_executado += executado
        total_sugerido += sugerido
        total_confirmado += confirmado
        linhas.append(linha)
    return {
        "titulo_plano": plano.titulo if plano is not None else "Plano de trabalho não associado",
        "revisao_plano": plano.get_status_revisao_display() if plano is not None else "",
        "valor_global": _moeda(plano.valor_global) if plano is not None and plano.valor_global is not None else "não informado",
        "valor_global_decimal": plano.valor_global if plano is not None else None,
        "executado": _moeda(total_executado),
        "executado_decimal": total_executado,
        "confirmado": _moeda(total_confirmado),
        "confirmado_decimal": total_confirmado,
        "sugerido": _moeda(total_sugerido),
        "sugerido_decimal": total_sugerido,
        "paginas": lote.quantidade_paginas,
        "pecas": lote.regioes.count(),
        "linhas": linhas,
        "cobertura": montar_cobertura(lote),
    }


def _linha_do_item(item, cadeias, somados_obrigacao, somados_sugerido, somados_confirmado):
    pecas = []
    codigos = set()
    executado = Decimal("0.00")
    sugerido = Decimal("0.00")
    confirmado = Decimal("0.00")
    regioes = []
    for cadeia in cadeias:
        partes = (
            (cadeia.execucao, "obrigacao"),
            (cadeia.apoio, "apoio"),
            (cadeia.comprovante, "comprovante"),
        )
        valores_cadeia = {}
        for regiao, papel in partes:
            if regiao is None:
                continue
            regioes.append(regiao)
            contribuicao = _contribuicao(
                regiao,
                papel,
                cadeia,
                somados_obrigacao,
                somados_sugerido,
                somados_confirmado,
            )
            if papel == "obrigacao" and contribuicao["soma"]:
                executado += contribuicao["valor"]
                valores_cadeia["obrigacao"] = contribuicao["valor"]
            elif papel == "comprovante" and contribuicao["soma"] and cadeia.estado == EstadoVinculo.CONFIRMADO:
                confirmado += contribuicao["valor"]
                valores_cadeia["comprovante"] = contribuicao["valor"]
            elif papel == "comprovante" and contribuicao["soma"] and cadeia.estado == EstadoVinculo.SUGERIDO:
                sugerido += contribuicao["valor"]
                valores_cadeia["comprovante"] = contribuicao["valor"]
            if contribuicao["codigo"]:
                codigos.add(contribuicao["codigo"])
            pecas.append(contribuicao["peca"])
        if (
            "obrigacao" in valores_cadeia
            and "comprovante" in valores_cadeia
            and valores_cadeia["obrigacao"] != valores_cadeia["comprovante"]
        ):
            codigos.add("divergencia")
        if cadeia.estado == EstadoVinculo.REJEITADO:
            codigos.add("rejeitada")
        elif cadeia.comprovante_id and cadeia.estado == EstadoVinculo.CONFIRMADO:
            codigos.add("confirmada")
        elif cadeia.comprovante_id and cadeia.estado == EstadoVinculo.SUGERIDO:
            codigos.add("sugerida")
        elif cadeia.execucao_id:
            codigos.add("sem_comprovante")
    situacao = _situacao(codigos, bool(pecas))
    pendencias = sum(1 for cadeia in cadeias if cadeia.estado == EstadoVinculo.SUGERIDO)
    vistas = set()
    for regiao in regioes:
        if regiao.pk in vistas:
            continue
        vistas.add(regiao.pk)
        pendencias += sum(1 for campo in regiao.campos.all() if campo.estado_revisao == EstadoCampo.PENDENTE)
    if item is None:
        descricao = "Documentos sem rubrica do plano"
        previsto = None
        revisao = ""
        ordem = None
        item_id = None
    else:
        descricao = item.descricao
        previsto = item.valor_previsto
        revisao = item.get_status_revisao_display()
        ordem = item.ordem
        item_id = item.id
    return (
        {
            "item_id": item_id,
            "ordem": ordem,
            "descricao": descricao,
            "revisao_item": revisao,
            "previsto": _moeda(previsto) if previsto is not None else "não informado",
            "previsto_decimal": previsto,
            "executado": _moeda(executado),
            "executado_decimal": executado,
            "sugerido": _moeda(sugerido),
            "sugerido_decimal": sugerido,
            "confirmado": _moeda(confirmado),
            "confirmado_decimal": confirmado,
            "situacao": _SITUACOES[situacao],
            "situacao_codigo": situacao,
            "explicacao": _explicacao(situacao),
            "documentos": len(vistas),
            "pendencias": pendencias,
            "aberto": bool(pecas),
            "pecas": pecas,
        },
        executado,
        sugerido,
        confirmado,
    )


def _contribuicao(regiao, papel, cadeia, somados_obrigacao, somados_sugerido, somados_confirmado) -> dict:
    chave = _CHAVES_OBRIGACAO.get(regiao.tipo_documental, "valor")
    if papel != "obrigacao":
        chave = "valor" if _campo(regiao, "valor") is not None else chave
    valor, ambiguo, original = _leitura(regiao, chave)
    soma = False
    codigo = ""
    nota = ""
    if papel == "apoio":
        nota = "Documento de apoio. Não entra na execução nem no pagamento."
    elif papel == "obrigacao":
        if regiao.pk in somados_obrigacao:
            nota = "Esta peça já entrou na execução. Não foi contada de novo."
            codigo = "insuficiente" if ambiguo else ""
        elif ambiguo or valor is None:
            nota = "Leitura ambígua ou valor não reconhecido. Não entrou na soma."
            codigo = "insuficiente"
            somados_obrigacao.add(regiao.pk)
        elif cadeia.estado == EstadoVinculo.REJEITADO:
            nota = "Vínculo rejeitado. O valor não entrou na soma."
            somados_obrigacao.add(regiao.pk)
        else:
            soma = True
            somados_obrigacao.add(regiao.pk)
    elif cadeia.estado == EstadoVinculo.REJEITADO:
        nota = "Vínculo rejeitado. O comprovante não entrou na soma."
    elif regiao.pk in somados_obrigacao or regiao.pk in somados_sugerido or regiao.pk in somados_confirmado:
        nota = "Esta peça já foi considerada. Não foi contada de novo."
    elif ambiguo or valor is None:
        nota = "Leitura ambígua ou valor não reconhecido. Não entrou na soma."
        codigo = "insuficiente"
    elif cadeia.estado == EstadoVinculo.CONFIRMADO:
        soma = True
        somados_confirmado.add(regiao.pk)
        nota = "Confirmado pelo auditor. Não aprova a despesa."
    else:
        soma = True
        somados_sugerido.add(regiao.pk)
        nota = "Sugestão automática. Não é pagamento confirmado."
    if regiao.tipo_documental == "guia_fgts" and papel == "obrigacao":
        nota = f"{nota} {_nota_guia(regiao, cadeia)}".strip()
    return {
        "soma": soma,
        "valor": valor or Decimal("0.00"),
        "codigo": codigo,
        "peca": {
            "papel": {"obrigacao": "Obrigação", "apoio": "Apoio", "comprovante": _papel_comprovante(cadeia.estado)}[papel],
            "rotulo": rotulo_tipo(regiao.tipo_documental),
            "pagina": regiao.pagina.numero_fisico,
            "peca_id": regiao.pk,
            "cadeia": cadeia.codigo,
            "valor": original or "não extraído",
            "nota": nota,
        },
    }
