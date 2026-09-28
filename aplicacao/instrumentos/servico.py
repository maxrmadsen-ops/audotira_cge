"""Persistência da extração, validação humana e congelamento."""

import logging
import re

from django.db import transaction
from django.utils import timezone

from aplicacao.instrumentos.escolhas import (
    CategoriaObrigacao,
    SituacaoExpectativa,
    StatusCampo,
    StatusValidacaoTermo,
)
from aplicacao.instrumentos.extracao import consistencia_aritmetica, extrair_termo
from aplicacao.instrumentos.models import (
    AplicacaoFinanceiraEsperada,
    CampoInstrumento,
    ClausulaInstrumento,
    ConsequenciaInstrumento,
    ContaBancariaEsperada,
    ObrigacaoInstrumento,
    ParteInstrumento,
    ReferenciaNormativaExtraida,
    RegraDerivadaInstrumento,
    RegraTemporal,
    TermoCongelado,
    TermoFomento,
    VersaoTermoCongelada,
)
from aplicacao.instrumentos.prompt_termo import garantir_prompt_termo, schema_aceita

logger = logging.getLogger("cge.instrumentos")


def termo_do_documento(documento):
    try:
        return documento.termo_fomento
    except TermoFomento.DoesNotExist:
        return None


def documento_congelado(documento) -> bool:
    termo = termo_do_documento(documento)
    return bool(termo and termo.congelado)


def estruturar_termo(documento):
    if documento_congelado(documento):
        raise TermoCongelado("Documento validado e congelado não é reprocessado por cima.")
    paginas = list(documento.paginas.order_by("numero_pagina"))
    texto = "\n".join(pagina.texto_extraido or "" for pagina in paginas)
    extraido = extrair_termo(texto)
    versao_prompt = garantir_prompt_termo()
    pacote = _pacote_schema(extraido)
    if not schema_aceita(pacote):
        raise ValueError("A extração não produziu a estrutura mínima.")
    with transaction.atomic():
        termo = termo_do_documento(documento)
        if termo is None:
            termo = TermoFomento(documento=documento, versao=1)
        else:
            _limpar(termo)
        _preencher(termo, documento, extraido, versao_prompt)
        termo.save()
        _gravar_filhos(termo, extraido, paginas)
        logger.info("extracao_termo documento=%s campos=%s", documento.pk, termo.campos.count())
    return termo


def confirmar_campo(campo: CampoInstrumento, usuario, observacao: str = ""):
    _exigir_aberto(campo.termo)
    campo.valor_validado = campo.valor_extraido
    campo.status = StatusCampo.VALIDADO
    campo.observacao = observacao
    campo.validado_por = usuario
    campo.validado_em = timezone.now()
    campo.termo.status_validacao = StatusValidacaoTermo.EM_VALIDACAO
    campo.termo.save(update_fields=["status_validacao", "atualizado_em"])
    campo.save()
    return campo


def corrigir_campo(campo: CampoInstrumento, usuario, valor: str, observacao: str = ""):
    _exigir_aberto(campo.termo)
    original = campo.valor_extraido
    campo.valor_validado = valor
    campo.status = StatusCampo.CORRIGIDO if valor != original else StatusCampo.VALIDADO
    campo.observacao = observacao
    campo.validado_por = usuario
    campo.validado_em = timezone.now()
    campo.termo.status_validacao = StatusValidacaoTermo.EM_VALIDACAO
    campo.termo.save(update_fields=["status_validacao", "atualizado_em"])
    campo.save()
    return campo


def marcar_nao_identificado(campo: CampoInstrumento, usuario, observacao: str = ""):
    _exigir_aberto(campo.termo)
    campo.valor_validado = ""
    campo.status = StatusCampo.NAO_IDENTIFICADO
    campo.observacao = observacao
    campo.validado_por = usuario
    campo.validado_em = timezone.now()
    campo.save()
    return campo


def congelar_termo(termo: TermoFomento, usuario, com_ressalvas: bool = False):
    if termo.congelado:
        raise TermoCongelado("O termo já está congelado.")
    conteudo = termo.conteudo_canonico()
    digest = termo.calcular_hash()
    termo.status_validacao = (
        StatusValidacaoTermo.VALIDADO_COM_RESSALVAS if com_ressalvas else StatusValidacaoTermo.VALIDADO
    )
    termo.validado_por = usuario
    termo.validado_em = timezone.now()
    termo.congelado = True
    termo.hash_congelado = digest
    termo.congelado_em = termo.validado_em
    termo.save()
    VersaoTermoCongelada.objects.create(
        termo=termo,
        numero=termo.versao,
        hash_conteudo=digest,
        conteudo=conteudo,
        congelado_por=usuario,
    )
    return termo


def abrir_nova_versao(termo: TermoFomento):
    if not termo.congelado:
        raise TermoCongelado("Só uma versão congelada abre a seguinte.")
    termo._liberar_congelamento = True
    termo.versao += 1
    termo.congelado = False
    termo.status_validacao = StatusValidacaoTermo.AGUARDANDO_VALIDACAO
    termo.save()
    return termo


def _exigir_aberto(termo: TermoFomento):
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")


def _limpar(termo: TermoFomento):
    termo.partes.all().delete()
    termo.clausulas.all().delete()
    termo.obrigacoes.all().delete()
    termo.regras_temporais.all().delete()
    termo.referencias_normativas.all().delete()
    termo.consequencias.all().delete()
    termo.regras_derivadas.all().delete()
    termo.campos.all().delete()
    AplicacaoFinanceiraEsperada.objects.filter(termo=termo).delete()
    ContaBancariaEsperada.objects.filter(termo=termo).delete()


def _preencher(termo, documento, extraido, versao_prompt):
    consistente, alerta = consistencia_aritmetica(
        extraido["quantidade_parcelas"],
        extraido["valor_parcela"],
        extraido["valor_total"],
    )
    termo.versao_prompt = versao_prompt
    termo.tipo_instrumento = extraido["tipo_instrumento"]
    termo.numero = extraido["numero"]
    termo.ano = extraido["ano"]
    termo.identificacao_completa = extraido["identificacao_completa"]
    termo.processo_sgpe = extraido["processo_sgpe"]
    termo.municipio = extraido["municipio"]
    termo.uf = extraido["uf"]
    termo.objeto_integral = extraido["objeto_integral"]
    termo.objeto_resumo = extraido["objeto_resumo"]
    termo.finalidade = extraido.get("finalidade", "")
    termo.destinacao_recursos = extraido.get("destinacao_recursos", "")
    termo.duracao_texto = extraido.get("duracao_texto", "")
    termo.referencia_plano_trabalho = extraido["referencia_plano_trabalho"]
    termo.moeda = extraido["moeda"]
    termo.valor_total = extraido["valor_total"]
    termo.valor_total_texto = extraido["valor_total_texto"]
    termo.quantidade_parcelas = extraido["quantidade_parcelas"]
    termo.valor_parcela = extraido["valor_parcela"]
    termo.valor_parcela_texto = extraido["valor_parcela_texto"]
    termo.consistente_aritmeticamente = consistente
    termo.alerta_aritmetico = alerta
    termo.metodo_extracao = "deterministico"
    termo.status_validacao = StatusValidacaoTermo.AGUARDANDO_VALIDACAO
    termo.demonstracao = bool(documento.demonstracao)
    termo.data_celebracao = extraido.get("data_celebracao")
    termo.data_assinatura = extraido.get("data_assinatura")
    termo.data_publicacao = extraido.get("data_publicacao")
    termo.vigencia_inicio = extraido.get("vigencia_inicio")
    termo.vigencia_fim = extraido.get("vigencia_fim")


def _gravar_filhos(termo, extraido, paginas):
    for parte in extraido["partes"]:
        if not parte["nome"] and not parte["cnpj"]:
            continue
        ParteInstrumento.objects.create(termo=termo, **parte)
    aplicacao_gravada = False
    conta_gravada = False
    for posicao, item in enumerate(extraido["clausulas"], start=1):
        pagina = _pagina_de(paginas, f"clausula {item['ordinal']}", item["texto"][:180])
        clausula = ClausulaInstrumento.objects.create(
            termo=termo,
            numero=item["numero"],
            ordinal=item["ordinal"],
            titulo=item["titulo"],
            texto=item["texto"],
            pagina=pagina,
            posicao=posicao,
            categoria=item["categoria"],
        )
        if item["obrigacao"]:
            obrigacao = ObrigacaoInstrumento.objects.create(
                termo=termo,
                clausula=clausula,
                situacao=SituacaoExpectativa.NAO_VERIFICAVEL,
                **item["obrigacao"],
            )
            RegraDerivadaInstrumento.objects.create(
                termo=termo,
                obrigacao=obrigacao,
                codigo=f"TERMO-OBRIG-{posicao:03d}",
                descricao=item["obrigacao"]["texto"][:500],
                conclusao="",
            )
        for regra in item["regras_temporais"]:
            RegraTemporal.objects.create(
                termo=termo,
                clausula=clausula,
                pagina=_pagina_de(paginas, regra.get("trecho", ""), item["texto"][:180]) or pagina,
                **regra,
            )
        if item["aplicacao"] and not aplicacao_gravada:
            AplicacaoFinanceiraEsperada.objects.create(
                termo=termo,
                clausula=clausula,
                situacao=SituacaoExpectativa.NAO_VERIFICAVEL,
                **item["aplicacao"],
            )
            aplicacao_gravada = True
        if item["conta"] and not conta_gravada:
            ContaBancariaEsperada.objects.create(termo=termo, clausula=clausula, **item["conta"])
            conta_gravada = True
        if item["consequencia"]:
            ConsequenciaInstrumento.objects.create(
                termo=termo,
                clausula=clausula,
                pagina=pagina,
                **item["consequencia"],
            )
    for referencia in extraido["referencias"]:
        ReferenciaNormativaExtraida.objects.create(
            termo=termo,
            pagina=_pagina_de(paginas, referencia["texto"]),
            trecho=referencia["texto"],
            **referencia,
        )
    _campos(termo, extraido, paginas)


def _campos(termo, extraido, paginas):
    concedente = next((parte for parte in extraido["partes"] if parte["papel"] == "concedente"), {})
    beneficiario = next((parte for parte in extraido["partes"] if parte["papel"] == "beneficiario"), {})
    conta = next((item["conta"] for item in extraido["clausulas"] if item["conta"]), {}) or {}
    restituicao = extraido.get("conta_restituicao") or {}
    trechos = extraido["trechos"]
    pares = (
        ("identificacao", "Identificação", extraido["identificacao_completa"], trechos["identificacao"]),
        ("processo", "Processo", extraido["processo_sgpe"], trechos["processo"]),
        ("concedente", "Concedente", concedente.get("nome", ""), concedente.get("nome", "")),
        ("beneficiario", "Beneficiário", beneficiario.get("nome", ""), beneficiario.get("nome", "")),
        ("municipio", "Município", extraido["municipio"], trechos["municipio"]),
        ("objeto", "Objeto", extraido["objeto_integral"], trechos["objeto"]),
        ("finalidade", "Finalidade", extraido.get("finalidade", ""), trechos.get("finalidade", "")),
        ("valor_total", "Valor", extraido["valor_total_texto"], trechos["valor_total"]),
        ("parcelas", "Parcelas", extraido["valor_parcela_texto"], trechos["parcelas"]),
        ("destinacao", "Destinação", extraido.get("destinacao_recursos", ""), trechos.get("destinacao", "")),
        ("vigencia_inicio", "Início da vigência", "", trechos.get("vigencia_inicio", "")),
        ("vigencia_fim", "Fim da vigência", extraido.get("duracao_texto", ""), trechos.get("vigencia_fim", "")),
        ("data_assinatura", "Data de assinatura", extraido.get("data_assinatura").isoformat() if extraido.get("data_assinatura") else "", trechos.get("data_assinatura", "")),
        ("data_publicacao", "Data de publicação", "", trechos.get("data_publicacao", "")),
        ("aplicacao_financeira", "Aplicação financeira", trechos.get("aplicacao", ""), trechos.get("aplicacao", "")),
        ("conta_instituicao", "Instituição da conta esperada", conta.get("instituicao", ""), trechos.get("conta", "")),
        ("conta_agencia", "Agência da conta esperada", conta.get("agencia", ""), trechos.get("conta_agencia", "")),
        ("conta_numero", "Número da conta esperada", conta.get("numero_conta", ""), trechos.get("conta_numero", "")),
        ("conta_restituicao", "Conta indicada para restituição", restituicao.get("texto", ""), trechos.get("conta_restituicao", "")),
    )
    for nome, rotulo, valor, trecho in pares:
        CampoInstrumento.objects.create(
            termo=termo,
            nome=nome,
            rotulo=rotulo,
            valor_extraido=valor or "",
            status=StatusCampo.AGUARDANDO if valor else StatusCampo.NAO_IDENTIFICADO,
            pagina=_pagina_de(paginas, trecho),
            trecho=trecho or "",
            metodo="deterministico",
        )


def _pagina_de(paginas, *trechos):
    from aplicacao.instrumentos.extracao import _normalizar

    for trecho in trechos:
        alvo = re.sub(r"\s+", " ", _normalizar(trecho or "")).lower().strip()
        if len(alvo) < 4:
            continue
        for pagina in paginas:
            corpo = re.sub(r"\s+", " ", _normalizar(pagina.texto_extraido or "")).lower()
            if len(alvo) < 16:
                if re.search(rf"\b{re.escape(alvo)}\b", corpo):
                    return pagina.numero_pagina
            elif alvo[:90] in corpo:
                return pagina.numero_pagina
    return None


def _pacote_schema(extraido: dict) -> dict:
    return {
        "identificacao": {
            "numero": extraido["numero"] or None,
            "ano": extraido["ano"],
            "processo": extraido["processo_sgpe"] or None,
        },
        "partes": extraido["partes"],
        "objeto": {"texto": extraido["objeto_integral"] or None},
        "recursos": {
            "valor_total": str(extraido["valor_total"]) if extraido["valor_total"] is not None else None,
            "quantidade_parcelas": extraido["quantidade_parcelas"],
            "valor_parcela": str(extraido["valor_parcela"]) if extraido["valor_parcela"] is not None else None,
        },
        "clausulas": extraido["clausulas"],
        "obrigacoes": [item["obrigacao"] for item in extraido["clausulas"] if item["obrigacao"]],
        "regras_temporais": [regra for item in extraido["clausulas"] for regra in item["regras_temporais"]],
        "aplicacao_financeira": next((item["aplicacao"] for item in extraido["clausulas"] if item["aplicacao"]), {}),
        "conta_bancaria": next((item["conta"] for item in extraido["clausulas"] if item["conta"]), {}),
        "referencias_normativas": extraido["referencias"],
        "consequencias": [item["consequencia"] for item in extraido["clausulas"] if item["consequencia"]],
        "proveniencia": [{"campo": nome, "trecho": trecho} for nome, trecho in extraido["trechos"].items()],
    }
