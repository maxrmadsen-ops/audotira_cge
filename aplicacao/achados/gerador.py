"""Transforma execuções de regra em sinalizações, evidências e achados potenciais."""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from aplicacao.achados.avaliacao import avaliar_fundamentacao, avaliar_rastreabilidade, registrar_avaliacao_nas_execucoes
from aplicacao.achados.consolidador import ancoras_da_execucao, chave_consolidacao, natureza_da_regra, tipo_da_sinalizacao
from aplicacao.achados.escolhas import (
    ConfiabilidadeOrigem,
    Criticidade,
    MetodoObtencao,
    NaturezaAchado,
    OrigemGeracao,
    PapelEvidencia,
    Prioridade,
    StatusAchado,
    TipoConstatacao,
    TipoEvidencia,
)
from aplicacao.achados.linguagem import texto_permitido
from aplicacao.achados.models import Achado, AchadoEvidencia, AchadoRegra, Evidencia, FundamentacaoAchado, Sinalizacao
from aplicacao.regras.escolhas import FONTE_EXCLUIDA_TESTE_CEGO, StatusTecnico

CENTAVOS = Decimal("0.01")
RESULTADOS_POSITIVOS = frozenset({"DEVOLVIDO"})
RESULTADOS_SEM_ACHADO = frozenset(
    {
        "CONFORME",
        "SEM DIVERGÊNCIA",
        "PRESENTE",
        "IDENTIFICADO",
        "EXISTE",
        "NÃO VERIFICÁVEL",
        "NÃO LOCALIZADO",
        "NÃO APLICÁVEL",
        "REQUER ANÁLISE SEMÂNTICA",
        "NÃO CONCLUSIVO",
        "NÃO GERAR",
        "ACHADO RASTREÁVEL",
        "FUNDAMENTADO",
        "INSUFICIENTE",
        "NÃO REALIZADA – ESCOPO DA V1",
        "EXCLUÍDO DO ESCOPO",
        "PENDENTE DE VALIDAÇÃO",
        "VALIDÁVEL",
        "NÃO VALIDÁVEL",
        "SALDO IDENTIFICADO",
        "NÃO IDENTIFICADA",
        "NORMAS IDENTIFICADAS",
    }
)


@dataclass
class ResumoGeracao:
    candidatos: int = 0
    consolidados: int = 0
    achados: int = 0
    erros: list[str] = field(default_factory=list)


def gerar_achados(analise_id: int) -> ResumoGeracao:
    from aplicacao.regras.models import ExecucaoAnalise

    analise = ExecucaoAnalise.objects.select_related("prestacao_contas").get(pk=analise_id)
    resumo = ResumoGeracao()
    grupos: dict[str, list] = {}
    for execucao in analise.execucoes.select_related("regra").prefetch_related("referencias", "calculos"):
        try:
            classe = classe_da_execucao(execucao)
            if classe is None:
                continue
            sinalizacao = _sinalizar(analise, execucao, classe)
            if sinalizacao is None:
                continue
            resumo.candidatos += 1
            grupos.setdefault(sinalizacao.chave_consolidacao, []).append((sinalizacao, classe))
        except Exception as erro:
            resumo.erros.append(f"{execucao.regra.codigo}: {erro}"[:300])
    for chave, itens in grupos.items():
        try:
            achado, criado = _consolidar(analise, chave, itens)
            if achado is not None:
                resumo.consolidados += 1
                if criado:
                    resumo.achados += 1
        except Exception as erro:
            resumo.erros.append(str(erro)[:300])
    registrar_avaliacao_nas_execucoes(analise)
    return resumo


def classe_da_execucao(execucao) -> str | None:
    texto = (execucao.resultado_funcional or "").strip()
    if texto in RESULTADOS_SEM_ACHADO or execucao.regra.codigo.startswith(("ACH-", "SYS-")):
        return None
    if texto in RESULTADOS_POSITIVOS:
        return "positiva"
    if execucao.status_tecnico == StatusTecnico.DIVERGENCIA or texto == "DIVERGÊNCIA":
        return "divergencia"
    if texto.startswith("POSSÍVEL"):
        return "atencao"
    return None


def documento_bloqueado(analise, documento) -> bool:
    if documento is None:
        return False
    if (documento.subtipo_documento or "") == FONTE_EXCLUIDA_TESTE_CEGO:
        return True
    excluidos = {item.get("documento_id") for item in (analise.documentos_excluidos or []) if isinstance(item, dict)}
    return documento.id in excluidos


def norma_vigente(norma, data_referencia) -> bool:
    if data_referencia is None:
        return norma.fim_vigencia is None
    if norma.inicio_vigencia and data_referencia < norma.inicio_vigencia:
        return False
    if norma.fim_vigencia and data_referencia > norma.fim_vigencia:
        return False
    return True


def _sinalizar(analise, execucao, classe: str) -> Sinalizacao | None:
    ancoras = ancoras_da_execucao(execucao)
    referencias_uteis = []
    for referencia in execucao.referencias.all():
        if referencia.documento_id and documento_bloqueado(analise, referencia.documento):
            continue
        referencias_uteis.append(referencia)
    calculos = list(execucao.calculos.all())
    if not referencias_uteis and not calculos and classe != "atencao":
        return None
    natureza = natureza_da_regra(execucao.regra)
    tipo = tipo_da_sinalizacao(classe)
    chave = chave_consolidacao(
        tipo_constatacao=tipo,
        natureza=natureza,
        ancoras=ancoras,
        codigo_regra=execucao.regra.codigo,
    )
    sinalizacao, criada = Sinalizacao.objects.get_or_create(
        execucao_regra=execucao,
        defaults={
            "analise": analise,
            "chave_consolidacao": chave,
            "descricao": execucao.regra.codigo,
            "demonstracao": bool(getattr(analise.prestacao_contas, "demonstracao", False)),
        },
    )
    if not criada and sinalizacao.achado_id is None and sinalizacao.chave_consolidacao != chave:
        sinalizacao.chave_consolidacao = chave
        sinalizacao.save(update_fields=["chave_consolidacao"])
    return sinalizacao


def _consolidar(analise, chave: str, itens: list) -> tuple[Achado | None, bool]:
    sinalizacao, classe = itens[0]
    execucao = sinalizacao.execucao_regra
    natureza = natureza_da_regra(execucao.regra)
    tipo = tipo_da_sinalizacao(classe)
    evidencias = []
    insuficiente = classe == "atencao"
    for item, _classe_item in itens:
        produzidas = _evidencias_da_execucao(analise, item.execucao_regra, tipo)
        if not produzidas and _classe_item == "divergencia":
            insuficiente = True
        evidencias.extend(produzidas)
    if not evidencias and classe != "atencao":
        return None, False
    if not evidencias:
        insuficiente = True
    materialidade = _materialidade(itens)
    criticidade = _criticidade(tipo, natureza, classe, insuficiente)
    prioridade = _prioridade(criticidade, materialidade)
    textos = _textos(itens, materialidade, insuficiente)
    with transaction.atomic():
        achado, criado = Achado.objects.get_or_create(
            analise=analise,
            chave_consolidacao=chave,
            defaults={
                "codigo": _novo_codigo(Achado, "ACH"),
                "prestacao_contas": analise.prestacao_contas,
                "titulo": textos["titulo"],
                "descricao_factual": textos["factual"],
                "interpretacao": textos["interpretacao"],
                "possivel_implicacao": textos["implicacao"],
                "categoria": execucao.regra.categoria,
                "natureza": natureza,
                "tipo_constatacao": tipo,
                "status": StatusAchado.POTENCIAL,
                "origem_geracao": OrigemGeracao.DETERMINISTICA,
                "materialidade_financeira": materialidade,
                "criticidade": criticidade,
                "prioridade": prioridade,
                "requer_analista": True,
                "evidencia_insuficiente": insuficiente,
                "demonstracao": bool(getattr(analise.prestacao_contas, "demonstracao", False)),
                "saida_original": textos,
            },
        )
        if criado and achado.status != StatusAchado.POTENCIAL:
            achado.status = StatusAchado.POTENCIAL
            achado.save(update_fields=["status"])
        for item, _classe_item in itens:
            AchadoRegra.objects.get_or_create(
                achado=achado,
                execucao=item.execucao_regra,
                defaults={"regra": item.execucao_regra.regra, "versao_regra": item.execucao_regra.regra.versao},
            )
            item.achado = achado
            item.save(update_fields=["achado"])
            _vincular_dominio(achado, item.execucao_regra)
            _fundamentar(achado, item.execucao_regra, analise.prestacao_contas.data_inicio)
        for evidencia, papel in evidencias:
            AchadoEvidencia.objects.get_or_create(achado=achado, evidencia=evidencia, defaults={"papel": papel})
        achado.elementos_rastreaveis = avaliar_rastreabilidade(achado)
        achado.fundamentacao_suficiente = avaliar_fundamentacao(achado)
        achado.save(update_fields=["elementos_rastreaveis", "fundamentacao_suficiente"])
    return achado, criado


def _evidencias_da_execucao(analise, execucao, tipo_constatacao: str) -> list[tuple[Evidencia, str]]:
    produzidas = []
    despesas = set()
    pagamentos = set()
    for referencia in execucao.referencias.all():
        if referencia.documento_id and documento_bloqueado(analise, referencia.documento):
            continue
        tipo, metodo, papel, confiabilidade = _classificar_referencia(referencia, tipo_constatacao)
        evidencia = _obter_evidencia(
            analise,
            execucao,
            tipo=tipo,
            metodo=metodo,
            trecho=(referencia.trecho or "")[:500],
            valor_textual=(referencia.valor_utilizado or "")[:255],
            documento=referencia.documento,
            pagina=referencia.pagina,
            hash_origem=(referencia.documento.hash_sha256 if referencia.documento_id else "")[:64],
            confiabilidade=confiabilidade,
            origem=referencia.tipo_fonte,
        )
        produzidas.append((evidencia, papel))
        if referencia.tipo_fonte == "despesa":
            despesas.add(referencia.identificador)
        if referencia.tipo_fonte == "pagamento":
            pagamentos.add(referencia.identificador)
    for calculo in execucao.calculos.all():
        evidencia = _obter_evidencia(
            analise,
            execucao,
            tipo=TipoEvidencia.CALCULADA,
            metodo=MetodoObtencao.CALCULO,
            trecho=calculo.operacao[:500],
            valor_textual=str(calculo.resultado)[:255],
            valor_numerico=calculo.resultado,
            confiabilidade=ConfiabilidadeOrigem.ALTA,
            origem="calculo",
            operandos=calculo.operandos or {},
        )
        papel = PapelEvidencia.SUPORTA if tipo_constatacao == TipoConstatacao.ACHADO_POTENCIAL else PapelEvidencia.CONTEXTUALIZA
        produzidas.append((evidencia, papel))
    if despesas and pagamentos:
        evidencia = _obter_evidencia(
            analise,
            execucao,
            tipo=TipoEvidencia.CRUZAMENTO,
            metodo=MetodoObtencao.CRUZAMENTO,
            trecho="Cruzamento entre despesa e pagamento já registrados na execução.",
            valor_textual="",
            confiabilidade=ConfiabilidadeOrigem.MEDIA,
            origem="cruzamento",
            operandos={"despesas": sorted(despesas), "pagamentos": sorted(pagamentos)},
        )
        produzidas.append((evidencia, PapelEvidencia.CONTEXTUALIZA))
    bloco_ia = (execucao.entradas or {}).get("ia") if isinstance(execucao.entradas, dict) else None
    if isinstance(bloco_ia, dict) and bloco_ia.get("justificativa"):
        evidencia = _obter_evidencia(
            analise,
            execucao,
            tipo=TipoEvidencia.SEMANTICA_IA,
            metodo=MetodoObtencao.AGENTE,
            trecho=str(bloco_ia.get("justificativa") or "")[:500],
            valor_textual="",
            confiabilidade=ConfiabilidadeOrigem.BAIXA,
            origem=str(bloco_ia.get("agente") or "agente")[:40],
        )
        produzidas.append((evidencia, PapelEvidencia.CONTEXTUALIZA))
    return produzidas


def _classificar_referencia(referencia, tipo_constatacao: str):
    if referencia.trecho_normativo_id:
        return TipoEvidencia.NORMATIVA, MetodoObtencao.NORMA, PapelEvidencia.FUNDAMENTA, ConfiabilidadeOrigem.ALTA
    if referencia.documento_id:
        return TipoEvidencia.DOCUMENTAL, MetodoObtencao.EXTRACAO, PapelEvidencia.SUPORTA, ConfiabilidadeOrigem.MEDIA
    papel = PapelEvidencia.CONTEXTUALIZA
    papel_origem = (referencia.papel_na_regra or "").casefold()
    if "contradiz" in papel_origem:
        papel = PapelEvidencia.CONTRADIZ
    elif "ausencia" in papel_origem:
        papel = PapelEvidencia.AUSENCIA
    if tipo_constatacao == TipoConstatacao.CONSTATACAO_POSITIVA:
        papel = PapelEvidencia.SUPORTA
    return TipoEvidencia.ESTRUTURADA, MetodoObtencao.MOTOR, papel, ConfiabilidadeOrigem.MEDIA


def _obter_evidencia(analise, execucao, **dados) -> Evidencia:
    consulta = {
        "execucao_regra": execucao,
        "tipo": dados["tipo"],
        "metodo_obtencao": dados["metodo"],
        "trecho": dados.get("trecho") or "",
        "valor_textual": dados.get("valor_textual") or "",
    }
    existente = Evidencia.objects.filter(**consulta).first()
    if existente is not None:
        return existente
    return Evidencia.objects.create(
        codigo=_novo_codigo(Evidencia, "EVD"),
        prestacao_contas=analise.prestacao_contas,
        tipo=dados["tipo"],
        origem=dados.get("origem") or "",
        documento=dados.get("documento"),
        pagina_documento=dados.get("pagina"),
        execucao_regra=execucao,
        trecho=consulta["trecho"],
        valor_textual=consulta["valor_textual"],
        valor_numerico=dados.get("valor_numerico"),
        hash_origem=dados.get("hash_origem") or "",
        metodo_obtencao=dados["metodo"],
        confiabilidade_origem=dados["confiabilidade"],
        operandos=dados.get("operandos") or {},
        demonstracao=bool(getattr(analise.prestacao_contas, "demonstracao", False)),
    )


def _fundamentar(achado, execucao, data_referencia) -> None:
    from aplicacao.normas.models import TrechoNormativo

    identificadores = [item.trecho_normativo_id for item in execucao.referencias.all() if item.trecho_normativo_id]
    if not identificadores:
        return
    for trecho in TrechoNormativo.objects.select_related("norma").filter(pk__in=identificadores):
        if not norma_vigente(trecho.norma, data_referencia):
            continue
        FundamentacaoAchado.objects.get_or_create(
            achado=achado,
            trecho_normativo=trecho,
            defaults={
                "norma": trecho.norma,
                "papel_fundamento": "elegivel",
                "vigencia_inicio": trecho.norma.inicio_vigencia,
                "vigencia_fim": trecho.norma.fim_vigencia,
                "origem_resolucao": "resolvedor_normativo",
            },
        )


def associar_fundamento(achado, trecho, data_referencia):
    if trecho is None or not norma_vigente(trecho.norma, data_referencia):
        return None
    fundamento, _criado = FundamentacaoAchado.objects.get_or_create(
        achado=achado,
        trecho_normativo=trecho,
        defaults={
            "norma": trecho.norma,
            "papel_fundamento": "elegivel",
            "vigencia_inicio": trecho.norma.inicio_vigencia,
            "vigencia_fim": trecho.norma.fim_vigencia,
            "origem_resolucao": "resolvedor_normativo",
        },
    )
    achado.fundamentacao_suficiente = avaliar_fundamentacao(achado)
    achado.save(update_fields=["fundamentacao_suficiente"])
    return fundamento


def _vincular_dominio(achado, execucao) -> None:
    from aplicacao.prestacoes_contas.models import Despesa, DocumentoFiscal, Pagamento

    for referencia in execucao.referencias.all():
        if not str(referencia.identificador or "").isdigit():
            continue
        identificador = int(referencia.identificador)
        if referencia.tipo_fonte == "despesa":
            despesa = Despesa.objects.filter(pk=identificador, prestacao=achado.prestacao_contas).first()
            if despesa is not None:
                achado.despesas.add(despesa)
        elif referencia.tipo_fonte == "documento_fiscal":
            fiscal = DocumentoFiscal.objects.filter(pk=identificador, prestacao=achado.prestacao_contas).first()
            if fiscal is not None:
                achado.documentos_fiscais.add(fiscal)
        elif referencia.tipo_fonte == "pagamento":
            pagamento = Pagamento.objects.filter(pk=identificador, prestacao=achado.prestacao_contas).first()
            if pagamento is not None:
                achado.pagamentos.add(pagamento)


def _materialidade(itens) -> Decimal | None:
    valores = []
    for sinalizacao, classe in itens:
        if classe == "positiva":
            continue
        for calculo in sinalizacao.execucao_regra.calculos.all():
            if calculo.unidade == "BRL" and calculo.operacao == "diferenca":
                valores.append(abs(Decimal(calculo.resultado)))
    if not valores:
        return None
    return max(valores).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _criticidade(tipo: str, natureza: str, classe: str, insuficiente: bool) -> str:
    if tipo == TipoConstatacao.CONSTATACAO_POSITIVA:
        return Criticidade.INFORMATIVA
    if insuficiente:
        return Criticidade.BAIXA
    if natureza == NaturezaAchado.VEDACAO and classe == "divergencia":
        return Criticidade.ALTA
    if classe == "divergencia":
        return Criticidade.MEDIA
    return Criticidade.BAIXA


def _prioridade(criticidade: str, materialidade: Decimal | None) -> str:
    if criticidade == Criticidade.ALTA:
        return Prioridade.ALTA
    if materialidade is not None and materialidade >= Decimal("1000.00"):
        return Prioridade.ALTA
    if materialidade is not None and materialidade > 0:
        return Prioridade.NORMAL
    return Prioridade.BAIXA


def _textos(itens, materialidade, insuficiente: bool) -> dict:
    codigos = ", ".join(item.execucao_regra.regra.codigo for item, _classe in itens)
    classe = itens[0][1]
    if classe == "positiva":
        titulo = "Devolução identificada nos registros estruturados."
        factual = "Os registros estruturados da prestação indicam devolução. Nenhum valor foi recalculado fora do motor."
        interpretacao = "Há constatação positiva de devolução identificada. Isso não conclui a prestação."
        implicacao = "O auditor pode conferir o comprovante antes de considerar a devolução conciliada."
    else:
        valor = f"R$ {materialidade}" if materialidade is not None else "valor não calculado nesta consolidação"
        titulo = "Possível divergência entre valores registrados."
        factual = f"As regras {codigos} registraram diferença calculada de {valor}. Os operandos permanecem na evidência calculada."
        interpretacao = "Foi identificada divergência entre os valores comparados pelas regras relacionadas."
        implicacao = "Requer avaliação do auditor quanto à existência de justificativa ou documentação complementar."
    if insuficiente:
        implicacao = "Evidência insuficiente — requer avaliação humana. " + implicacao
    return {
        "titulo": texto_permitido(titulo)[:300],
        "factual": texto_permitido(factual),
        "interpretacao": texto_permitido(interpretacao),
        "implicacao": texto_permitido(implicacao),
    }


def _novo_codigo(modelo, prefixo: str) -> str:
    ultimo = modelo.objects.order_by("-id").values_list("codigo", flat=True).first()
    numero = 1
    if ultimo and ultimo.startswith(prefixo + "-"):
        try:
            numero = int(ultimo.split("-", 1)[1]) + 1
        except ValueError:
            numero = modelo.objects.count() + 1
    return f"{prefixo}-{numero:06d}"
