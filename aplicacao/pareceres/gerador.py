"""Monta a pré-análise a partir dos fatos já apurados. A IA só redige quando é chamada."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.pareceres.contexto import montar_contexto
from aplicacao.pareceres.escolhas import (
    EncaminhamentoPreAnalise,
    ORDEM_SECAO,
    OrigemConteudo,
    StatusPreAnalise,
    StatusValidacaoAfirmacao,
    TipoAfirmacao,
    TipoSecao,
)
from aplicacao.pareceres.models import AfirmacaoPreAnalise, FonteAfirmacaoPreAnalise, PreAnaliseTecnica, SecaoPreAnalise
from aplicacao.pareceres.validador import ValidadorProvenienciaPreAnalise

NAO_OFICIAIS = {StatusValidacaoAfirmacao.NAO_SUPORTADA, StatusValidacaoAfirmacao.REJEITADA}


class ErroGeracaoPreAnalise(Exception):
    pass


def gerar_pre_analise(analise, usuario=None, gerenciador=None, demonstracao=False) -> PreAnaliseTecnica:
    prestacao = analise.prestacao_contas
    with transaction.atomic():
        versao = (
            PreAnaliseTecnica.objects.filter(prestacao_contas=prestacao, execucao_analise=analise).aggregate(Max("versao"))[
                "versao__max"
            ]
            or 0
        ) + 1
        pre = PreAnaliseTecnica.objects.create(
            codigo=_codigo(),
            prestacao_contas=prestacao,
            execucao_analise=analise,
            versao=versao,
            status=StatusPreAnalise.GERANDO,
            titulo=f"Pré-análise técnica — {prestacao.numero_processo}",
            solicitada_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            demonstracao=demonstracao or bool(getattr(prestacao, "demonstracao", False)),
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.GERACAO_PRE_ANALISE,
        descricao="Solicitação de geração da pré-análise.",
        usuario=usuario,
        detalhes={"codigo": pre.codigo, "versao": pre.versao, "fase": "solicitacao"},
    )
    try:
        contexto = montar_contexto(analise)
        _preencher(pre, contexto)
        if gerenciador is not None:
            _aplicar_ia(pre, contexto, gerenciador)
        pre.status = StatusPreAnalise.AGUARDANDO_REVISAO
        pre.gerada_em = timezone.now()
        pre.save()
        registrar_evento(
            evento=RegistroAuditoria.Evento.GERACAO_PRE_ANALISE,
            descricao="Geração da pré-análise concluída.",
            usuario=usuario,
            detalhes={"codigo": pre.codigo, "versao": pre.versao, "fase": "concluida", "status": pre.status},
        )
    except Exception as erro:
        pre.status = StatusPreAnalise.ERRO
        pre.diagnostico_ia = {"erro": str(erro)[:300]}
        pre.save(update_fields=["status", "diagnostico_ia", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.ERRO_PROCESSAMENTO,
            descricao="Falha controlada na geração da pré-análise.",
            usuario=usuario,
            detalhes={"codigo": pre.codigo, "erro": str(erro)[:300]},
        )
        raise ErroGeracaoPreAnalise(str(erro)[:300]) from erro
    return pre


def _preencher(pre: PreAnaliseTecnica, contexto: dict) -> None:
    prestacao = contexto["prestacao"]
    documentos = contexto["documentos"]
    verificacoes = contexto["verificacoes"]
    achados = contexto["achados"]
    fonte_prestacao = _item(contexto, prestacao["numero_processo"])
    identificacao = _secao(pre, TipoSecao.IDENTIFICACAO)
    _afirmar(
        identificacao,
        1,
        TipoAfirmacao.FATO,
        (
            f"Prestação {prestacao['numero_processo']}. "
            f"Concedente: {prestacao['concedente'] or 'não informado'}. "
            f"Beneficiário: {prestacao['beneficiario'] or 'não informado'}. "
            f"Período: {prestacao['data_inicio'] or '—'} a {prestacao['data_fim'] or '—'}."
        ),
        [fonte_prestacao],
    )
    escopo = _secao(pre, TipoSecao.ESCOPO_ANALISE)
    pre.escopo = (
        "A pré-análise organiza fatos, cálculos, evidências e achados já produzidos pelo sistema. "
        "Ela não aprova, não reprova e não declara a prestação regular ou irregular."
    )
    _afirmar(escopo, 1, TipoAfirmacao.CONTEXTO, pre.escopo, [fonte_prestacao])
    documentacao = _secao(pre, TipoSecao.DOCUMENTACAO_ANALISADA)
    fontes_documentos = [_item(contexto, registro["nome"]) for registro in documentos["registros"]]
    _afirmar(
        documentacao,
        1,
        TipoAfirmacao.CONTEXTO,
        (
            f"Documentos recebidos: {documentos['recebidos']}. Processados: {documentos['processados']}. "
            f"Validados: {documentos['validados']}. Aguardando validação: {documentos['aguardando_validacao']}. "
            f"Com erro: {documentos['com_erro']}. Tipos presentes: {', '.join(documentos['tipos']) or 'nenhum'}."
        ),
        fontes_documentos or [fonte_prestacao],
    )
    normas = _secao(pre, TipoSecao.REFERENCIAL_NORMATIVO)
    if contexto["normas"]:
        for ordem, norma in enumerate(contexto["normas"], start=1):
            _afirmar(
                normas,
                ordem,
                TipoAfirmacao.FUNDAMENTACAO,
                (
                    f"Norma elegível {norma['identificador']}, vigência {norma['vigencia_inicio'] or '—'} a {norma['vigencia_fim'] or 'em vigor'}. "
                    f"Dispositivo {norma['artigo'] or 'não informado'}."
                ),
                [_item(contexto, norma["identificador"])],
            )
    else:
        _afirmar(normas, 1, TipoAfirmacao.LIMITACAO, "Nenhuma norma elegível foi vinculada aos achados desta execução.", [fonte_prestacao])
    verificacao = _secao(pre, TipoSecao.VERIFICACOES_REALIZADAS)
    partes = [f"{resultado}: {total}" for resultado, total in sorted(verificacoes["por_resultado"].items())]
    _afirmar(
        verificacao,
        1,
        TipoAfirmacao.CONTEXTO,
        (
            f"Regras cadastradas: {verificacoes['regras_cadastradas']}. "
            f"Execuções com resultado: {verificacoes['executadas']}. "
            f"Distribuição: {'; '.join(partes) or 'nenhuma execução'}."
        ),
        [fonte_prestacao],
    )
    if verificacoes["por_resultado"].get("NÃO VERIFICÁVEL"):
        _afirmar(
            verificacao,
            2,
            TipoAfirmacao.LIMITACAO,
            "Há regra com resultado NÃO VERIFICÁVEL. Esse resultado não foi convertido em irregularidade.",
            [fonte_prestacao],
        )
    achados_secao = _secao(pre, TipoSecao.ACHADOS_CONSTATACOES)
    ordem = 1
    for achado in achados:
        fontes = _fontes_achado(contexto, achado)
        if achado["tipo_constatacao"] == "constatacao_positiva":
            _afirmar(
                achados_secao,
                ordem,
                TipoAfirmacao.CONSTATACAO_POSITIVA,
                f"Foi identificada constatação positiva suportada em {achado['codigo']}: {achado['factual']}",
                fontes,
            )
        else:
            materialidade = _dinheiro(achado["materialidade"])
            regras = ", ".join(regra["codigo"] for regra in achado["regras"]) or "sem regra vinculada"
            valor = f" A materialidade financeira registrada é de {materialidade}." if materialidade else ""
            _afirmar(
                achados_secao,
                ordem,
                TipoAfirmacao.ACHADO,
                (
                    f"{achado['codigo']} — {achado['titulo']}. {achado['factual']}{valor} "
                    f"Regras relacionadas: {regras}. Situação: {achado['status']}. "
                    f"Criticidade: {achado['criticidade']}. Prioridade: {achado['prioridade']}. "
                    "O achado potencial não foi confirmado automaticamente e permanece sujeito à avaliação do auditor."
                ),
                fontes,
            )
        ordem += 1
        if achado["suporta"] and achado["contradiz"]:
            _afirmar(
                achados_secao,
                ordem,
                TipoAfirmacao.FATO,
                (
                    f"O achado {achado['codigo']} possui evidências que suportam ({', '.join(achado['suporta'])}) "
                    f"e evidências que contradizem ({', '.join(achado['contradiz'])}). "
                    "Os elementos divergentes não foram ocultados e exigem avaliação humana."
                ),
                fontes,
            )
            ordem += 1
        for fundamento in achado["fundamentos"]:
            _afirmar(
                achados_secao,
                ordem,
                TipoAfirmacao.FUNDAMENTACAO,
                f"Fundamentação de {achado['codigo']}: {fundamento['identificador']}, dispositivo {fundamento['artigo'] or '—'}.",
                [_item(contexto, fundamento["identificador"]), _item(contexto, achado["codigo"])],
            )
            ordem += 1
    if not achados:
        _afirmar(achados_secao, 1, TipoAfirmacao.CONTEXTO, "Nenhum achado foi consolidado nesta execução.", [fonte_prestacao])
    limitacoes = _limitacoes(contexto)
    secao_limitacoes = _secao(pre, TipoSecao.LIMITACOES)
    for ordem, texto in enumerate(limitacoes, start=1):
        _afirmar(secao_limitacoes, ordem, TipoAfirmacao.LIMITACAO, texto, [fonte_prestacao])
    pre.limitacoes = " ".join(limitacoes)
    humana = _secao(pre, TipoSecao.PONTOS_AVALIACAO_HUMANA)
    pontos = [achado for achado in achados if achado["status"] != "confirmado" or achado["evidencia_insuficiente"] or achado["contradiz"]]
    if pontos:
        for ordem, achado in enumerate(pontos, start=1):
            _afirmar(
                humana,
                ordem,
                TipoAfirmacao.LIMITACAO,
                f"{achado['codigo']} requer avaliação humana. Situação atual: {achado['status']}.",
                [_item(contexto, achado["codigo"])],
            )
    else:
        _afirmar(humana, 1, TipoAfirmacao.CONTEXTO, "Não há ponto adicional de avaliação humana além da revisão desta pré-análise.", [fonte_prestacao])
    sintese = _secao(pre, TipoSecao.SINTESE, OrigemConteudo.DETERMINISTICO)
    pre.resumo_executivo = _sintese(achados, verificacoes)
    _afirmar(sintese, 1, TipoAfirmacao.CONTEXTO, pre.resumo_executivo, [fonte_prestacao] + [_item(contexto, achado["codigo"]) for achado in achados])
    pre.encaminhamento = _encaminhamento(achados, limitacoes)
    secao_encaminhamento = _secao(pre, TipoSecao.ENCAMINHAMENTO)
    _afirmar(
        secao_encaminhamento,
        1,
        TipoAfirmacao.ENCAMINHAMENTO,
        f"Encaminhamento permitido: {pre.get_encaminhamento_display()}. A decisão administrativa permanece com o auditor.",
        [fonte_prestacao],
    )
    pre.save(update_fields=["escopo", "limitacoes", "resumo_executivo", "encaminhamento", "atualizado_em"])


def _aplicar_ia(pre, contexto, gerenciador) -> None:
    from aplicacao.pareceres.agente import AgentePreAnaliseTecnica

    chamada = AgentePreAnaliseTecnica(gerenciador).redigir(
        contexto, prestacao=pre.prestacao_contas, analise=pre.execucao_analise, chave=pre.codigo
    )
    resposta = chamada.resposta or {}
    pre.provedor = chamada.provedor or ""
    pre.versao_prompt_id = chamada.usos[0].versao_prompt_id if chamada.usos else None
    pre.modelo_inteligencia_artificial = chamada.usos[0].modelo if chamada.usos else None
    pre.diagnostico_ia = {
        "status": chamada.status,
        "erro": chamada.erro,
        "resultado": resposta.get("resultado", ""),
        "governada": bool(resposta.get("governada")),
        "diagnostico_estrutural": resposta.get("diagnostico_estrutural") or [],
        "fontes_rejeitadas": resposta.get("fontes_rejeitadas", []),
        "tentativas": len(chamada.usos),
    }
    validador = ValidadorProvenienciaPreAnalise(contexto)
    proveniencia = []
    if resposta.get("texto_rejeitado"):
        _registrar_ia(pre, resposta["texto_rejeitado"], StatusValidacaoAfirmacao.REJEITADA, "Conclusão ou encaminhamento não permitido.", [])
    elif resposta.get("resumo"):
        avaliacao = validador.validar_afirmacao(resposta["resumo"], TipoAfirmacao.CONTEXTO, [])
        if avaliacao.status in {StatusValidacaoAfirmacao.REJEITADA, StatusValidacaoAfirmacao.NAO_SUPORTADA}:
            proveniencia.append("proveniencia_invalida")
        _registrar_ia(pre, resposta["resumo"], avaliacao.status, avaliacao.motivo, [])
    for secao in resposta.get("secoes") or []:
        for afirmacao in secao.get("afirmacoes") or []:
            texto = str(afirmacao.get("texto") or "")
            tipo = _tipo_afirmacao(afirmacao.get("tipo"))
            fontes = afirmacao.get("fontes") or []
            avaliacao = validador.validar_afirmacao(texto, tipo, fontes)
            if avaliacao.status in {StatusValidacaoAfirmacao.REJEITADA, StatusValidacaoAfirmacao.NAO_SUPORTADA}:
                proveniencia.append("proveniencia_invalida")
            _registrar_ia(pre, texto, avaliacao.status, avaliacao.motivo, avaliacao.fontes_aceitas or [])
    if proveniencia:
        pre.diagnostico_ia["proveniencia"] = ["proveniencia_invalida"]
    elif resposta.get("governada"):
        pre.diagnostico_ia["proveniencia"] = ["proveniencia_valida"]
    else:
        pre.diagnostico_ia["proveniencia"] = []
    if validador.encaminhamento_permitido(str(resposta.get("encaminhamento") or "")):
        pre.encaminhamento = resposta["encaminhamento"]
    pre.save(update_fields=["provedor", "versao_prompt", "modelo_inteligencia_artificial", "diagnostico_ia", "encaminhamento", "atualizado_em"])


def _registrar_ia(pre, texto, status, motivo, fontes) -> None:
    secao = pre.secoes.get(tipo=TipoSecao.SINTESE)
    ordem = secao.afirmacoes.count() + 1
    oficial = status not in NAO_OFICIAIS
    _afirmar(
        secao,
        ordem,
        TipoAfirmacao.CONTEXTO,
        texto,
        fontes,
        origem=OrigemConteudo.IA,
        status=status,
        oficial=oficial,
        original=texto,
        motivo=motivo,
    )


def _limitacoes(contexto: dict) -> list[str]:
    documentos = contexto["documentos"]
    verificacoes = contexto["verificacoes"]
    textos = []
    if documentos["aguardando_validacao"]:
        textos.append(f"Há {documentos['aguardando_validacao']} documento(s) aguardando validação.")
    if documentos["com_erro"]:
        textos.append(f"Há {documentos['com_erro']} documento(s) com falha de processamento.")
    if documentos["ocr_qualidade_insuficiente"]:
        textos.append(f"Há {documentos['ocr_qualidade_insuficiente']} página(s) com OCR de qualidade insuficiente.")
    if verificacoes["por_resultado"].get("NÃO VERIFICÁVEL"):
        textos.append("Há regra não verificável. A ausência de verificação não foi tratada como irregularidade.")
    if verificacoes["por_resultado"].get("NÃO REALIZADA – ESCOPO DA V1") or verificacoes["por_resultado"].get("EXCLUÍDO DO ESCOPO"):
        textos.append("Há regra fora do escopo desta versão.")
    for achado in contexto["achados"]:
        if achado["evidencia_insuficiente"]:
            textos.append(f"{achado['codigo']} possui evidência insuficiente e requer avaliação humana.")
        if achado["suporta"] and achado["contradiz"]:
            textos.append(f"{achado['codigo']} apresenta evidências contraditórias.")
    if not textos:
        textos.append("Não foram identificadas limitações relevantes nos dados apurados desta execução.")
    return textos


def _sintese(achados: list, verificacoes: dict) -> str:
    potenciais = [achado for achado in achados if achado["tipo_constatacao"] != "constatacao_positiva"]
    positivas = [achado for achado in achados if achado["tipo_constatacao"] == "constatacao_positiva"]
    materiais = [achado for achado in potenciais if achado["materialidade"]]
    insuficientes = [achado for achado in achados if achado["evidencia_insuficiente"]]
    partes = ["A análise automatizada organizou os resultados já apurados."]
    if potenciais:
        partes.append(f"Foram identificados {len(potenciais)} achado(s) potencial(is), ainda sujeitos à avaliação humana.")
    if materiais:
        partes.append("Há materialidade financeira registrada de " + ", ".join(_dinheiro(achado["materialidade"]) for achado in materiais) + ".")
    if positivas:
        partes.append(f"Há {len(positivas)} constatação(ões) positiva(s) suportada(s).")
    if insuficientes:
        partes.append("Há situação com evidência insuficiente que requer avaliação humana.")
    if verificacoes["por_resultado"].get("NÃO VERIFICÁVEL"):
        partes.append("Resultado não verificável não foi tratado como irregularidade.")
    partes.append("Esta síntese não constitui decisão sobre a prestação de contas.")
    return " ".join(partes)


def _encaminhamento(achados: list, limitacoes: list[str]) -> str:
    relevantes = [texto for texto in limitacoes if not texto.startswith("Não foram identificadas")]
    if achados or relevantes:
        return EncaminhamentoPreAnalise.SUBMETER_AO_AUDITOR
    return EncaminhamentoPreAnalise.PROSSEGUIR_ANALISE


def _fontes_achado(contexto, achado) -> list:
    fontes = [_item(contexto, achado["codigo"])]
    for regra in achado["regras"]:
        fontes.append(_item(contexto, regra["codigo"]))
    for evidencia in achado["evidencias"]:
        fontes.append(_item(contexto, evidencia["codigo"]))
    for calculo in achado["calculos"]:
        fontes.append(_item(contexto, f"CALC-{calculo['pk']}"))
    for fundamento in achado["fundamentos"]:
        fontes.append(_item(contexto, fundamento["identificador"]))
    return [fonte for fonte in fontes if fonte]


def _item(contexto, identificador):
    for item in contexto["itens"]:
        if item.get("identificador") == identificador and item.get("tipo") != "referencia":
            return item
    return None


def _secao(pre, tipo, origem=OrigemConteudo.DETERMINISTICO) -> SecaoPreAnalise:
    secao, _ = SecaoPreAnalise.objects.get_or_create(
        pre_analise=pre,
        tipo=tipo,
        defaults={"ordem": ORDEM_SECAO[tipo], "titulo": TipoSecao(tipo).label, "origem_conteudo": origem},
    )
    return secao


def _afirmar(secao, ordem, tipo, texto, fontes, origem=OrigemConteudo.DETERMINISTICO, status=StatusValidacaoAfirmacao.VALIDADA, oficial=True, original="", motivo="") -> AfirmacaoPreAnalise:
    afirmacao = AfirmacaoPreAnalise.objects.create(
        secao=secao,
        ordem=ordem,
        tipo=tipo,
        texto_original_ia=original,
        texto_atual=texto,
        status_validacao=status,
        origem_conteudo=origem,
        exibir_oficial=oficial,
        motivo_rejeicao=motivo[:300],
    )
    for fonte in fontes or []:
        if not fonte:
            continue
        FonteAfirmacaoPreAnalise.objects.create(
            afirmacao=afirmacao,
            codigo_fonte=str(fonte.get("identificador") or "")[:80],
            tipo_fonte=str(fonte.get("tipo") or "")[:40],
            evidencia_id=fonte.get("pk") if fonte.get("tipo") == "evidencia" else None,
            achado_id=fonte.get("pk") if fonte.get("tipo") == "achado" else None,
            regra_id=fonte.get("pk") if fonte.get("tipo") == "regra" else None,
            execucao_regra_id=fonte.get("execucao_id") if fonte.get("tipo") == "regra" else None,
            norma_id=fonte.get("pk") if fonte.get("tipo") == "norma" else None,
            trecho_normativo_id=fonte.get("trecho_id") if fonte.get("tipo") == "norma" else None,
            documento_id=fonte.get("documento_id") or (fonte.get("pk") if fonte.get("tipo") == "documento" else None),
            pagina=fonte.get("pagina"),
            calculo_id=fonte.get("pk") if fonte.get("tipo") == "calculo" else None,
        )
    return afirmacao


def _tipo_afirmacao(valor) -> str:
    bruto = str(valor or "").casefold()
    for item in TipoAfirmacao.values:
        if item == bruto:
            return item
    return TipoAfirmacao.CONTEXTO


def _dinheiro(valor: str) -> str:
    if not valor:
        return ""
    try:
        quantizado = Decimal(valor).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return ""
    return f"R$ {quantizado:.2f}".replace(".", ",")


def _codigo() -> str:
    ultimo = PreAnaliseTecnica.objects.order_by("-id").values_list("codigo", flat=True).first()
    numero = 1
    if ultimo and ultimo.startswith("PA-"):
        try:
            numero = int(ultimo.split("-", 1)[1]) + 1
        except ValueError:
            numero = PreAnaliseTecnica.objects.count() + 1
    return f"PA-{numero:06d}"
