"""Helpers de apresentação do inventário e da conferência."""

from __future__ import annotations

from aplicacao.laboratorio.escolhas import EstadoClassificacao, EstadoRevisao
from aplicacao.laboratorio.models import InventarioPagina


def eh_placeholder(regiao) -> bool:
    """Menção sem documento ou página inteira inconclusiva. Não é peça efetiva."""
    return regiao.tipo_documental == "outros_nao_classificados" or regiao.metodo_deteccao == "pagina_inteira_inconclusiva"


def filtrar_paginas(lote, get) -> list[InventarioPagina]:
    consulta = lote.paginas.all()
    peca = (get.get("peca") or "").strip()
    if peca.isdigit():
        consulta = consulta.filter(regioes__pk=int(peca))
    pagina = (get.get("pagina") or "").strip()
    if pagina.isdigit():
        consulta = consulta.filter(numero_fisico=int(pagina))
    tipo = (get.get("tipo") or "").strip()
    if tipo:
        consulta = consulta.filter(tipos_candidatos__contains=[tipo])
    classificacao = (get.get("classificacao") or "").strip()
    if classificacao == "sugerida":
        consulta = consulta.filter(estado_classificacao=EstadoClassificacao.PROPOSTO)
    elif classificacao == "confirmada":
        consulta = consulta.filter(
            estado_classificacao__in=(EstadoClassificacao.CONFIRMADO, EstadoClassificacao.CORRIGIDO)
        )
    elif classificacao == "inconclusiva":
        consulta = consulta.filter(estado_classificacao=EstadoClassificacao.INCONCLUSIVO)
    qualidade = (get.get("qualidade") or "").strip()
    if qualidade:
        consulta = consulta.filter(qualidade_extracao=qualidade)
    tecnica = (get.get("tecnica") or "").strip()
    if tecnica:
        consulta = consulta.filter(tecnica_utilizada=tecnica)
    revisao = (get.get("revisao") or "").strip()
    if revisao == "pendente":
        consulta = consulta.filter(estado_revisao=EstadoRevisao.PENDENTE)
    elif revisao == "concluida":
        consulta = consulta.filter(estado_revisao=EstadoRevisao.REVISADA)
    elif revisao == "ilegivel":
        consulta = consulta.filter(estado_revisao=EstadoRevisao.ILEGIVEL)
    if (get.get("inspecao") or "").strip() == "sim":
        from aplicacao.laboratorio.models import RevisaoLaboratorio

        numeros = RevisaoLaboratorio.objects.filter(
            lote=lote, alvo="descoberta_pagina", acao="inspecao_ocr"
        ).values("alvo_id")
        consulta = consulta.filter(numero_fisico__in=numeros)
    return list(consulta.select_related("pagina_documento").prefetch_related("regioes").distinct())


def resumo_pagina(pagina: InventarioPagina) -> str:
    regioes = [r for r in pagina.regioes.all() if r.tipo_documental != "outros_nao_classificados"]
    if not regioes and not pagina.tipos_candidatos:
        return "Sem classificação conclusiva"
    if not regioes:
        return "Candidatos sem peça segmentada: " + ", ".join(pagina.tipos_candidatos)
    from aplicacao.laboratorio.catalogo import rotulo_tipo

    return " · ".join(f"{rotulo_tipo(r.tipo_documental)}" for r in regioes)


def campos_uteis(regiao) -> list:
    """Remove campos genéricos vazios ou sem valor estruturado útil."""
    uteis = []
    for campo in regiao.campos.all():
        if campo.chave in {"titulo", "observacao"} and (
            not campo.valor_original or campo.valor_original.strip().isdigit() or len(campo.valor_original.strip()) < 3
        ):
            continue
        if not campo.valor_original and not campo.obrigatorio:
            continue
        uteis.append(campo)
    return uteis


def campos_conferencia(regiao) -> list:
    """Mantém o campo vazio obrigatório visível e omite título genérico sem texto."""
    itens = []
    for campo in regiao.campos.all():
        if campo.chave in {"titulo", "observacao"} and not (campo.valor_original or "").strip():
            continue
        itens.append(campo)
    return itens


def rotulo_metodo(metodo: str, estado_classificacao: str = "") -> str:
    confirmada = estado_classificacao in {EstadoClassificacao.CONFIRMADO, EstadoClassificacao.CORRIGIDO}
    if metodo == "ajuste_humano":
        if confirmada:
            return "Região ajustada pelo auditor"
        return "Região ajustada pelo auditor — revisão pendente"
    if confirmada:
        return "Separação conferida"
    return "Separação automática preliminar — revisão pendente"


SECOES_PECA = {
    "comprovante_transferencia": (
        ("contas", "Identificação e contas", (
            "instituicao", "titular_origem", "agencia_origem", "conta_origem",
            "beneficiario", "agencia_destino", "conta_destino", "dados_destino",
        )),
        ("operacao", "Dados da operação", (
            "tipo_operacao", "data_hora", "hora_operacao", "data_hora_impressao", "valor",
            "numero_documento", "numero_documento_adicional",
        )),
        ("autenticacao", "Autenticação", ("autenticacao", "situacao", "identificadores")),
    ),
    "holerite": (
        ("partes", "Empregador e trabalhadora", ("empregador", "cnpj_empregador", "funcionario")),
        ("funcional", "Dados funcionais", (
            "matricula", "cargo", "cbo", "data_admissao", "competencia", "referencia_pagamento",
        )),
        ("proventos", "Proventos", ("salario_base", "total_proventos")),
        ("descontos", "Descontos", ("inss", "irrf", "total_descontos")),
        ("bases", "Bases e encargos", (
            "base_inss", "base_fgts", "fgts_mes", "base_irrf", "bases_calculo", "valor_liquido", "liquido_calculado",
        )),
        ("assinaturas", "Assinaturas e atestos", (
            "data_recebimento", "assinaturas", "responsavel_atesto", "cpf_atesto",
        )),
    ),
    "termo_rescisao": (
        ("partes", "Partes", ("trabalhador", "empregador", "motivo")),
        ("datas", "Datas", ("data_admissao", "data_aviso", "data_desligamento")),
        ("totais", "Totais", ("total_bruto", "deducoes", "total_liquido", "liquido_calculado")),
        ("verbas", "Verbas e deduções", ("verbas_rescisorias",)),
        ("assinaturas", "Assinaturas", ("assinaturas",)),
    ),
    "termo_quitacao": (
        ("partes", "Partes", ("trabalhador", "empregador")),
        ("datas", "Datas do contrato", ("data_admissao", "data_aviso", "data_afastamento", "data")),
        ("quitacao", "Quitação", ("valor_quitado", "assinaturas")),
    ),
    "comunicacao_dispensa": (
        ("partes", "Partes", ("trabalhador", "empregador")),
        ("dispensa", "Dispensa", ("data_comunicacao", "protocolo", "motivo", "comprovante_recebimento")),
    ),
}


CHAVES_RUBRICA_AGREGADA = {"rubricas_proventos", "rubricas_descontos"}


def _campo_excepcional(campo) -> bool:
    if getattr(campo, "estado_confianca", "") == "inconsistente":
        return True
    return getattr(campo, "estado_confianca", "") == "parcial" and not (getattr(campo, "valor_original", "") or "").strip()


def secoes_da_peca(tipo: str, campos: list, rubricas_estruturadas: bool = False) -> list[dict]:
    por_chave = {campo.chave: campo for campo in campos}
    definicao = SECOES_PECA.get(tipo) or (("campos", "Campos extraídos", tuple(por_chave)),)
    usadas = set()
    secoes = []
    for codigo, titulo, chaves in definicao:
        itens = []
        for chave in chaves:
            campo = por_chave.get(chave)
            if campo is None:
                continue
            if not campo.valor_original and not campo.obrigatorio and campo.estado_confianca not in {"ambiguo", "inconsistente", "parcial"} and campo.chave not in {
                "cpf_atesto", "autenticacao", "salario_base", "hora_operacao", "data_hora_impressao", "matricula", "data_recebimento",
                "total_liquido", "liquido_calculado", "assinaturas", "deducoes", "total_bruto", "valor_quitado",
                "data_comunicacao", "protocolo", "motivo", "data_admissao", "data_aviso", "data_afastamento", "data",
            }:
                continue
            itens.append(campo)
            usadas.add(chave)
        pendentes = sum(1 for item in itens if item.estado_revisao == "pendente" or (item.obrigatorio and not item.valor_original))
        if not itens:
            continue
        excecoes = sum(1 for item in itens if _campo_excepcional(item))
        secoes.append({"codigo": codigo, "titulo": titulo, "campos": itens, "pendentes": pendentes, "excecoes": excecoes})
    resto = [
        campo
        for campo in campos
        if campo.chave not in usadas
        and (campo.valor_original or campo.obrigatorio)
        and not (rubricas_estruturadas and campo.chave in CHAVES_RUBRICA_AGREGADA)
    ]
    if resto:
        secoes.append(
            {
                "codigo": "outros",
                "titulo": "Outros campos",
                "campos": resto,
                "pendentes": sum(1 for item in resto if item.estado_revisao == "pendente"),
                "excecoes": sum(1 for item in resto if _campo_excepcional(item)),
            }
        )
    return secoes


def resumo_peca(regiao) -> dict:
    valores = {campo.chave: campo.valor_original for campo in regiao.campos.all()}
    if regiao.tipo_documental == "comprovante_transferencia":
        return {
            "tipo": "Comprovante de transferência",
            "pessoa": valores.get("beneficiario") or "Beneficiário não localizado",
            "referencia": valores.get("data_hora") or "Data não localizada",
            "valor": valores.get("valor") or "Valor não localizado",
        }
    if regiao.tipo_documental == "holerite":
        return {
            "tipo": "Holerite",
            "pessoa": valores.get("funcionario") or "Trabalhadora não localizada",
            "referencia": valores.get("competencia") or "Competência não localizada",
            "valor": valores.get("valor_liquido") or "Líquido não localizado",
        }
    if regiao.tipo_documental == "termo_rescisao":
        lido = valores.get("total_liquido") or ""
        calculado = valores.get("liquido_calculado") or ""
        if lido and calculado:
            valor = f"Lido {lido} · calculado {calculado}"
        elif lido:
            valor = f"Lido {lido}"
        elif calculado:
            valor = f"Calculado {calculado}"
        else:
            valor = "Líquido não localizado"
        return {
            "tipo": "Termo de rescisão",
            "pessoa": valores.get("trabalhador") or "Trabalhador não localizado",
            "referencia": valores.get("data_desligamento") or "Desligamento não localizado",
            "valor": valor,
        }
    if regiao.tipo_documental == "termo_quitacao":
        return {
            "tipo": "Termo de quitação",
            "pessoa": valores.get("trabalhador") or "Trabalhador não localizado",
            "referencia": valores.get("data_afastamento") or "Afastamento não lido",
            "valor": valores.get("valor_quitado") or "Valor não consta no termo",
        }
    if regiao.tipo_documental == "comunicacao_dispensa":
        return {
            "tipo": "Comunicação de dispensa",
            "pessoa": valores.get("trabalhador") or "Trabalhador não localizado",
            "referencia": valores.get("protocolo") or "Protocolo não identificado",
            "valor": valores.get("data_comunicacao") or "Data da comunicação pendente de leitura",
        }
    from aplicacao.laboratorio.catalogo import rotulo_tipo

    return {
        "tipo": rotulo_tipo(regiao.tipo_documental),
        "pessoa": "",
        "referencia": "",
        "valor": "",
    }


def comparar_pagina(regioes) -> dict | None:
    from decimal import Decimal, InvalidOperation

    from aplicacao.laboratorio.extracao import texto_moeda

    holerite = next((regiao for regiao in regioes if regiao.tipo_documental == "holerite"), None)
    transferencia = next((regiao for regiao in regioes if regiao.tipo_documental == "comprovante_transferencia"), None)
    if holerite is None or transferencia is None:
        return None

    def ler(regiao, chave):
        campo = next((item for item in regiao.campos.all() if item.chave == chave), None)
        if campo is None:
            return None, ""
        texto = (campo.valor_normalizado or campo.valor_original or "").strip()
        try:
            return Decimal(texto), campo.estado_revisao
        except (InvalidOperation, ValueError):
            return None, campo.estado_revisao

    liquido, estado_liquido = ler(holerite, "valor_liquido")
    valor, estado_valor = ler(transferencia, "valor")
    proventos, _estado_proventos = ler(holerite, "total_proventos")
    descontos, _estado_descontos = ler(holerite, "total_descontos")
    calculado = proventos - descontos if proventos is not None and descontos is not None else None
    nomes = _correspondencia_nomes(
        next((item.valor_original for item in transferencia.campos.all() if item.chave == "beneficiario"), ""),
        next((item.valor_original for item in holerite.campos.all() if item.chave == "funcionario"), ""),
    )
    return {
        "liquido": texto_moeda(liquido) if liquido is not None else "não extraído",
        "transferencia": texto_moeda(valor) if valor is not None else "não extraído",
        "proventos": texto_moeda(proventos) if proventos is not None else "não extraído",
        "descontos": texto_moeda(descontos) if descontos is not None else "não extraído",
        "calculado": texto_moeda(calculado) if calculado is not None else "não calculado",
        "valores_iguais": liquido is not None and valor is not None and liquido == valor,
        "aritmetica_ok": calculado is not None and liquido is not None and calculado == liquido,
        "nomes": nomes,
        "estado_humano": "pendente"
        if "pendente" in {estado_liquido, estado_valor}
        else (estado_liquido or estado_valor or "pendente"),
        "origem_liquido": f"Holerite · página {holerite.pagina.numero_fisico}",
        "origem_transferencia": f"Comprovante · página {transferencia.pagina.numero_fisico}",
        **_conferir_rubricas(holerite, proventos, descontos),
    }


def _conferir_rubricas(holerite, total_proventos, total_descontos) -> dict:
    from decimal import Decimal, InvalidOperation

    from aplicacao.laboratorio.extracao import texto_moeda

    def somar(natureza: str):
        valores = []
        for rubrica in holerite.rubricas.all():
            if rubrica.natureza != natureza:
                continue
            texto = (rubrica.valor_normalizado or "").strip()
            if not texto:
                return None
            try:
                valores.append(Decimal(texto))
            except (InvalidOperation, ValueError):
                return None
        if not valores:
            return None
        return sum(valores, Decimal("0"))

    def estado(soma, total):
        if soma is None or total is None:
            return "inconclusivo"
        if soma == total:
            return "confere"
        return "divergente"

    soma_proventos = somar("provento")
    soma_descontos = somar("desconto")
    return {
        "soma_proventos": texto_moeda(soma_proventos) if soma_proventos is not None else "não extraída",
        "soma_proventos_estado": estado(soma_proventos, total_proventos),
        "soma_descontos": texto_moeda(soma_descontos) if soma_descontos is not None else "não extraída",
        "soma_descontos_estado": estado(soma_descontos, total_descontos),
    }


def _correspondencia_nomes(beneficiario: str, trabalhadora: str) -> str:
    tokens_a = {parte for parte in (beneficiario or "").upper().split() if len(parte) > 2}
    tokens_b = {parte for parte in (trabalhadora or "").upper().split() if len(parte) > 2}
    if not tokens_a or not tokens_b:
        return "Nome ausente em uma das peças. Correspondência não sugerida."
    if tokens_a <= tokens_b or tokens_b <= tokens_a or len(tokens_a & tokens_b) >= 2:
        return (
            f"{beneficiario} no comprovante e {trabalhadora} no holerite. "
            "Correspondência sugerida — revisão pendente."
        )
    return (
        f"{beneficiario} no comprovante e {trabalhadora} no holerite. "
        "Os nomes diferem. Correspondência sugerida — revisão pendente."
    )
