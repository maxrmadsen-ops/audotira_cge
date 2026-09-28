"""Ficha genérica de extração. O termo de fomento é o primeiro tipo especializado."""

from django.core.exceptions import ObjectDoesNotExist

from aplicacao.auditoria.models import RegistroAuditoria

GRUPOS_CAMPOS = (
    ("Identificação do instrumento", ("identificacao", "processo", "municipio")),
    ("Partes envolvidas", ("concedente", "beneficiario")),
    ("Objeto e finalidade", ("objeto", "finalidade", "destinacao")),
    ("Recursos financeiros", ("valor_total", "parcelas")),
    ("Vigência e regras temporais", ("vigencia_inicio", "vigencia_fim", "data_assinatura", "data_publicacao")),
    ("Aplicação financeira dos recursos", ("aplicacao_financeira",)),
    ("Conta bancária e movimentação financeira", ("conta_instituicao", "conta_agencia", "conta_numero", "conta_restituicao")),
)
NATUREZA_OBRIGACAO = "Obrigação prevista no instrumento. O cumprimento não foi verificado."
CLASSE = {
    "extraido": "ficha-extraido",
    "aguardando_validacao": "ficha-aguardando",
    "validado": "ficha-validado",
    "corrigido": "ficha-corrigido",
    "nao_identificado": "ficha-neutro",
    "nao_aplicavel": "ficha-neutro",
    "obrigacao_prevista": "ficha-extraido",
}
ROTULO = {
    "extraido": "Extraído",
    "aguardando_validacao": "Aguardando validação",
    "validado": "Validado",
    "corrigido": "Corrigido",
    "nao_identificado": "Não identificado",
    "nao_aplicavel": "Não aplicável",
    "obrigacao_prevista": "Obrigação prevista no instrumento",
}


def montar_ficha(documento, termo=None, dados=None) -> dict:
    ocr = documento.paginas.filter(necessitou_ocr=True).exists() if documento.pk else False
    grupos = _grupos_termo(documento, termo, ocr) if termo is not None else _grupos_genericos(documento, dados, ocr)
    return {
        "grupos": grupos,
        "classificacao": _classificacao(documento),
        "metadados": _metadados(documento, termo, ocr),
    }


def _classificacao(documento) -> dict:
    ultimo = (
        RegistroAuditoria.objects.filter(
            evento__in=(RegistroAuditoria.Evento.VALIDACAO_HUMANA, RegistroAuditoria.Evento.RECLASSIFICACAO),
            detalhes__documento=documento.pk,
        )
        .order_by("-id")
        .first()
    )
    justificativa = ""
    if ultimo and isinstance(ultimo.detalhes, dict):
        justificativa = ultimo.detalhes.get("justificativa") or ""
    confianca = documento.confianca_classificacao
    return {
        "tipo": documento.subtipo_documento or documento.get_tipo_documento_display(),
        "tipo_documental": documento.get_tipo_documento_display(),
        "metodo": documento.get_metodo_classificacao_display(),
        "fundamento": documento.fundamento_classificacao,
        "validada": documento.classificacao_validada,
        "confianca": confianca if confianca else None,
        "justificativa": justificativa,
    }


def _metadados(documento, termo, ocr: bool) -> dict:
    if termo is None:
        return {
            "metodo": "OCR" if ocr else "Leitura do arquivo",
            "capturado_em": documento.criado_em,
            "prompt": "",
            "modelo": "",
            "versao": "",
        }
    prompt = ""
    if termo.versao_prompt_id:
        prompt = f"{termo.versao_prompt.prompt.codigo} v{termo.versao_prompt.versao} registrado e não utilizado nesta extração"
    return {
        "metodo": _metodo("deterministico", ocr),
        "capturado_em": termo.criado_em,
        "prompt": prompt,
        "modelo": "Nenhum modelo de IA foi chamado.",
        "versao": str(termo.versao),
    }


def _grupos_genericos(documento, dados, ocr: bool) -> list[dict]:
    linhas = []
    for dado in dados or []:
        pagina = dado.pagina.numero_pagina if dado.pagina_id else None
        linhas.append(
            _linha(
                rotulo=dado.get_tipo_display(),
                valor_extraido=dado.valor,
                documento=documento.nome_original,
                pagina=pagina,
                trecho=dado.trecho,
                metodo=dado.metodo or ("OCR" if ocr else "Leitura do arquivo"),
                capturado_em=dado.criado_em,
                confianca=dado.confianca,
                situacao="extraido",
                natureza="Candidato extraído. Não é fato validado.",
            )
        )
    if not linhas:
        linhas.append(
            _linha(
                rotulo="Informação estruturada",
                documento=documento.nome_original,
                metodo="OCR" if ocr else "Leitura do arquivo",
                capturado_em=documento.criado_em,
                situacao="nao_identificado",
            )
        )
    return [{"titulo": "Dados extraídos do documento", "linhas": linhas}]


def _grupos_termo(documento, termo, ocr: bool) -> list[dict]:
    campos = {campo.nome: campo for campo in termo.campos.all()}
    usados = set()
    grupos = []
    for titulo, nomes in GRUPOS_CAMPOS:
        linhas = [_linha_campo(documento, termo, campos[nome], ocr) for nome in nomes if nome in campos]
        usados.update(nomes)
        if titulo == "Partes envolvidas":
            linhas.extend(_linhas_partes(documento, termo, ocr))
        if titulo == "Vigência e regras temporais":
            linhas.extend(_linhas_temporais(documento, termo, ocr))
        if titulo == "Aplicação financeira dos recursos":
            linhas.extend(_linhas_aplicacao(documento, termo, ocr))
        if titulo == "Conta bancária e movimentação financeira":
            linhas.extend(_linhas_conta(documento, termo, ocr))
        grupos.append({"titulo": titulo, "linhas": linhas or [_vazia(documento, termo, ocr)]})
    restantes = [_linha_campo(documento, termo, campo, ocr) for nome, campo in campos.items() if nome not in usados]
    if restantes:
        grupos.append({"titulo": "Outros dados extraídos", "linhas": restantes})
    grupos.extend(
        [
            {"titulo": "Obrigações do concedente", "linhas": _linhas_obrigacoes(documento, termo, ocr, "concedente")},
            {"titulo": "Obrigações do beneficiário/convenente", "linhas": _linhas_obrigacoes(documento, termo, ocr, "beneficiario")},
            {"titulo": "Normas e referências legais citadas", "linhas": _linhas_normas(documento, termo, ocr)},
            {"titulo": "Penalidades, consequências e condições", "linhas": _linhas_consequencias(documento, termo, ocr)},
            {"titulo": "Regras derivadas para verificações posteriores", "linhas": _linhas_regras(documento, termo, ocr)},
        ]
    )
    _anexar_fontes(grupos, documento, termo, ocr)
    return grupos


def _linha_campo(documento, termo, campo, ocr: bool) -> dict:
    situacao = campo.status or "aguardando_validacao"
    natureza = ""
    if campo.nome == "aplicacao_financeira" and campo.valor_extraido:
        situacao = "obrigacao_prevista"
        natureza = NATUREZA_OBRIGACAO
    return _linha(
        rotulo=campo.rotulo,
        valor_extraido=campo.valor_extraido,
        valor_validado=campo.valor_validado,
        documento=documento.nome_original,
        pagina=campo.pagina,
        trecho=campo.trecho,
        metodo=_metodo(campo.metodo, ocr),
        capturado_em=termo.criado_em,
        situacao=situacao if campo.valor_extraido or campo.status != "aguardando_validacao" else "nao_identificado",
        campo_id=campo.pk,
        observacao=campo.observacao,
        responsavel=str(campo.validado_por) if campo.validado_por_id else "",
        validado_em=campo.validado_em,
        versao=str(termo.versao),
        natureza=natureza,
    )


def _linhas_partes(documento, termo, ocr: bool) -> list[dict]:
    linhas = []
    for parte in termo.partes.all():
        for rotulo, valor in (
            (f"CNPJ do {parte.get_papel_display().lower()}", parte.cnpj),
            (f"Representante do {parte.get_papel_display().lower()}", parte.representante_nome),
        ):
            linhas.append(
                _linha(
                    rotulo=rotulo,
                    valor_extraido=valor,
                    documento=documento.nome_original,
                    metodo=_metodo("deterministico", ocr),
                    capturado_em=termo.criado_em,
                    situacao="extraido" if valor else "nao_identificado",
                    versao=str(termo.versao),
                )
            )
    return linhas


def _linhas_temporais(documento, termo, ocr: bool) -> list[dict]:
    linhas = []
    for regra in termo.regras_temporais.select_related("clausula"):
        ordinal = regra.clausula.ordinal if regra.clausula_id else ""
        valor = " ".join(
            str(parte)
            for parte in (regra.quantidade, regra.get_unidade_display(), regra.get_operador_display(), regra.evento_destino)
            if parte
        )
        if regra.data_documental and not regra.quantidade:
            valor = f"Data documental {regra.data_documental.strftime('%d/%m/%Y')}"
        linhas.append(
            _linha(
                rotulo=f"Regra temporal da cláusula {ordinal or '—'}",
                valor_extraido=valor,
                documento=documento.nome_original,
                pagina=regra.pagina,
                trecho=regra.trecho,
                metodo=_metodo("deterministico", ocr),
                capturado_em=termo.criado_em,
                situacao="extraido" if valor else "nao_identificado",
                versao=str(termo.versao),
                natureza=regra.calculo or "Prazo relativo. Nenhuma data foi calculada.",
                destaque=ordinal in {"QUINTA", "SEXTA", "SETIMA"},
            )
        )
    return linhas


def _relacionado(termo, nome: str):
    try:
        return getattr(termo, nome)
    except ObjectDoesNotExist:
        return None


def _linhas_aplicacao(documento, termo, ocr: bool) -> list[dict]:
    aplicacao = _relacionado(termo, "aplicacao_financeira")
    if aplicacao is None:
        return []
    pagina = aplicacao.clausula.pagina if aplicacao.clausula_id else None
    return [
        _linha(
            rotulo="Aplicação financeira exigida pelo instrumento",
            valor_extraido=aplicacao.texto,
            documento=documento.nome_original,
            pagina=pagina,
            trecho=aplicacao.texto,
            metodo=_metodo("deterministico", ocr),
            capturado_em=termo.criado_em,
            situacao="obrigacao_prevista" if aplicacao.texto else "nao_identificado",
            versao=str(termo.versao),
            natureza=NATUREZA_OBRIGACAO,
            destaque=True,
        )
    ]


def _linhas_conta(documento, termo, ocr: bool) -> list[dict]:
    conta = _relacionado(termo, "conta_bancaria")
    if conta is None:
        return []
    pagina = conta.clausula.pagina if conta.clausula_id else None
    return [
        _linha(
            rotulo="Conta de movimentação prevista",
            valor_extraido=" · ".join(parte for parte in (conta.instituicao, conta.agencia, conta.numero_conta) if parte),
            documento=documento.nome_original,
            pagina=pagina,
            trecho=conta.texto,
            metodo=_metodo("deterministico", ocr),
            capturado_em=termo.criado_em,
            situacao="obrigacao_prevista" if conta.texto else "nao_identificado",
            versao=str(termo.versao),
            natureza="Conta prevista no instrumento. A movimentação não foi comprovada.",
        )
    ]


def _linhas_obrigacoes(documento, termo, ocr: bool, papel: str) -> list[dict]:
    linhas = []
    for obrigacao in termo.obrigacoes.select_related("clausula"):
        if obrigacao.categoria == "aplicacao_financeira":
            continue
        sujeito = (obrigacao.sujeito or "").lower()
        if papel == "concedente" and "concedente" not in sujeito:
            continue
        if papel == "beneficiario" and not any(sinal in sujeito for sinal in ("benefici", "convenente", "associa")):
            continue
        ordinal = obrigacao.clausula.ordinal if obrigacao.clausula_id else ""
        pagina = obrigacao.clausula.pagina if obrigacao.clausula_id else None
        linhas.append(
            _linha(
                rotulo=f"Cláusula {ordinal or '—'} · {obrigacao.get_categoria_display()}",
                valor_extraido=obrigacao.texto,
                documento=documento.nome_original,
                pagina=pagina,
                trecho=obrigacao.texto,
                metodo=_metodo("deterministico", ocr),
                capturado_em=termo.criado_em,
                situacao="obrigacao_prevista" if obrigacao.texto else "nao_identificado",
                versao=str(termo.versao),
                natureza=NATUREZA_OBRIGACAO,
                destaque=ordinal in {"QUINTA", "SEXTA", "SETIMA"},
            )
        )
    return linhas or [_vazia(documento, termo, ocr)]


def _linhas_normas(documento, termo, ocr: bool) -> list[dict]:
    linhas = []
    for referencia in termo.referencias_normativas.all():
        linhas.append(
            _linha(
                rotulo=referencia.texto,
                valor_extraido=referencia.texto,
                documento=documento.nome_original,
                pagina=referencia.pagina,
                trecho=referencia.trecho or referencia.texto,
                metodo=_metodo("deterministico", ocr),
                capturado_em=termo.criado_em,
                situacao="extraido",
                versao=str(termo.versao),
                natureza=referencia.get_status_correspondencia_display() + ". Citação no instrumento; norma oficial não foi criada.",
            )
        )
    return linhas or [_vazia(documento, termo, ocr)]


def _linhas_consequencias(documento, termo, ocr: bool) -> list[dict]:
    linhas = []
    for item in termo.consequencias.select_related("clausula"):
        ordinal = item.clausula.ordinal if item.clausula_id else ""
        linhas.append(
            _linha(
                rotulo=f"Consequência da cláusula {ordinal or '—'}",
                valor_extraido=item.texto,
                documento=documento.nome_original,
                pagina=item.pagina,
                trecho=item.trecho or item.texto,
                metodo=_metodo("deterministico", ocr),
                capturado_em=termo.criado_em,
                situacao="obrigacao_prevista" if item.texto else "nao_identificado",
                versao=str(termo.versao),
                natureza="Condição prevista no instrumento. Não é registro de descumprimento.",
                destaque=ordinal in {"QUINTA", "SEXTA", "SETIMA"},
            )
        )
    return linhas or [_vazia(documento, termo, ocr)]


def _anexar_fontes(grupos: list[dict], documento, termo, ocr: bool) -> None:
    por_titulo = {grupo["titulo"]: grupo for grupo in grupos}
    for clausula in termo.clausulas.all():
        if clausula.ordinal not in {"QUINTA", "SEXTA", "SETIMA"}:
            continue
        titulo = _destino_clausula(clausula)
        por_titulo[titulo]["linhas"].append(
            _linha(
                rotulo=f"Texto-fonte da cláusula {clausula.ordinal}",
                valor_extraido=clausula.texto,
                documento=documento.nome_original,
                pagina=clausula.pagina,
                trecho=clausula.texto,
                metodo=_metodo("deterministico", ocr),
                capturado_em=termo.criado_em,
                situacao="extraido" if clausula.texto else "nao_identificado",
                versao=str(termo.versao),
                natureza="Texto-fonte da cláusula. A interpretação não substitui o documento.",
                destaque=True,
            )
        )


def _destino_clausula(clausula) -> str:
    texto = f"{clausula.titulo} {clausula.texto}".lower()
    if clausula.categoria == "aplicacao_financeira" or ("aplica" in texto and "financeira" in texto):
        return "Aplicação financeira dos recursos"
    if clausula.categoria == "penalidade" or "suspens" in texto:
        return "Penalidades, consequências e condições"
    if clausula.categoria == "conta_bancaria":
        return "Conta bancária e movimentação financeira"
    if clausula.categoria == "recursos" or "transfer" in texto:
        return "Recursos financeiros"
    return "Vigência e regras temporais"


def _linhas_regras(documento, termo, ocr: bool) -> list[dict]:
    linhas = []
    for regra in termo.regras_derivadas.all():
        linhas.append(
            _linha(
                rotulo=regra.codigo,
                valor_extraido=regra.descricao,
                documento=documento.nome_original,
                metodo=_metodo("deterministico", ocr),
                capturado_em=termo.criado_em,
                situacao="extraido",
                versao=str(termo.versao),
                natureza="Regra derivada para verificação posterior. Conclusão de auditoria não atribuída.",
            )
        )
    return linhas or [_vazia(documento, termo, ocr)]


def _vazia(documento, termo, ocr: bool) -> dict:
    return _linha(
        rotulo="Informação do grupo",
        documento=documento.nome_original,
        metodo=_metodo("deterministico", ocr),
        capturado_em=termo.criado_em,
        situacao="nao_identificado",
        versao=str(termo.versao),
    )


def _metodo(codigo: str, ocr: bool) -> str:
    if codigo == "deterministico":
        return "Determinístico sobre texto com OCR" if ocr else "Determinístico"
    return codigo or "Não registrado"


def _linha(**dados) -> dict:
    linha = {
        "rotulo": "",
        "valor_extraido": "",
        "valor_validado": "",
        "documento": "",
        "pagina": None,
        "trecho": "",
        "busca": "",
        "metodo": "",
        "capturado_em": None,
        "confianca": None,
        "situacao": "nao_identificado",
        "situacao_rotulo": ROTULO["nao_identificado"],
        "classe": CLASSE["nao_identificado"],
        "campo_id": None,
        "observacao": "",
        "responsavel": "",
        "validado_em": None,
        "versao": "",
        "natureza": "",
        "destaque": False,
    }
    linha.update(dados)
    situacao = linha["situacao"] if linha["situacao"] in ROTULO else "extraido"
    if not linha["valor_extraido"] and situacao in {"extraido", "aguardando_validacao"}:
        situacao = "nao_identificado"
    linha["situacao"] = situacao
    linha["situacao_rotulo"] = ROTULO[situacao]
    linha["classe"] = CLASSE[situacao]
    trecho = " ".join((linha["trecho"] or "").split())
    linha["trecho"] = trecho
    linha["busca"] = trecho[:80]
    return linha
