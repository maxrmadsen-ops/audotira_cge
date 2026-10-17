"""Organiza o plano para a tela. Não grava e não altera o estado da revisão."""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode

from django.urls import reverse

from aplicacao.prestacoes_contas.escolhas import NaturezaItem, StatusRevisaoPlano

SECOES = ("resumo", "metas", "despesas", "cronograma", "documento")
ROTULOS_SECAO = (
    ("resumo", "Resumo"),
    ("metas", "Metas e etapas"),
    ("despesas", "Despesas previstas"),
    ("cronograma", "Cronograma"),
    ("documento", "Documento original"),
)
SIGLAS_MES = {
    "janeiro": "Jan",
    "fevereiro": "Fev",
    "março": "Mar",
    "marco": "Mar",
    "abril": "Abr",
    "maio": "Mai",
    "junho": "Jun",
    "julho": "Jul",
    "agosto": "Ago",
    "setembro": "Set",
    "outubro": "Out",
    "novembro": "Nov",
    "dezembro": "Dez",
}


def etapas_legiveis(etapas: str, parametros: str = "") -> str:
    """Tira cabeçalhos e a continuação que veio grudada nos parâmetros. O original continua guardado."""

    texto = _apos_afericao(_limpar(etapas))
    if not texto:
        return ""
    parametros_limpos = _apos_afericao(_limpar(parametros))
    _, continuacao = _dividir_frase_grudada(parametros_limpos)
    if parametros_limpos and texto.startswith(parametros_limpos):
        resto = texto[len(parametros_limpos) :].strip(" .:-")
        if resto:
            return resto
    if continuacao:
        return continuacao
    _, texto_continuacao = _dividir_frase_grudada(texto)
    if texto_continuacao:
        return texto_continuacao
    if parametros_limpos and parametros_limpos in texto:
        resto = texto[texto.find(parametros_limpos) + len(parametros_limpos) :].strip(" .:-")
        if resto:
            return resto
    return texto


def parametros_legiveis(parametros: str) -> str:
    """Mostra só os parâmetros quando a frase seguinte veio colada depois do ponto."""

    texto = _apos_afericao(_limpar(parametros))
    base, continuacao = _dividir_frase_grudada(texto)
    if continuacao:
        return base
    return texto


def recorte_evidencia(trecho: str, valor: str = "", limite: int = 160) -> str:
    texto = _limpar(trecho)
    if not texto:
        return ""
    ancora = _limpar(valor)[:80]
    if ancora and ancora in texto:
        indice = texto.find(ancora)
        inicio = max(0, indice - 24)
        return texto[inicio : inicio + limite].strip()
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].strip()


def resumo_descricao(descricao: str, limite: int = 110) -> str:
    texto = _limpar(descricao)
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].strip() + "…"


def montar_contexto_plano(request, prestacao, plano) -> dict:
    secao = request.GET.get("secao") or "resumo"
    if secao not in SECOES:
        secao = "resumo"
    busca = (request.GET.get("q") or "").strip()
    estado = request.GET.get("estado") or ""
    natureza = request.GET.get("natureza") or ""
    ordem = request.GET.get("ordem") or "padrao"
    if estado not in {"", StatusRevisaoPlano.AGUARDANDO, StatusRevisaoPlano.CONFIRMADO, StatusRevisaoPlano.CORRIGIDO, StatusRevisaoPlano.REJEITADO}:
        estado = ""
    if natureza not in {"", *NaturezaItem.values}:
        natureza = ""
    if ordem not in {"padrao", "valor", "descricao", "estado"}:
        ordem = "padrao"

    itens = list(plano.itens.all())
    metas = list(plano.metas.all())
    from aplicacao.prestacoes_contas.situacao_revisao import avaliar_lote, chaves_ratificacao, rotulo_revisao

    chaves = chaves_ratificacao(prestacao)
    visiveis = []
    for item in itens:
        if busca and busca.lower() not in (item.descricao or "").lower() and busca.lower() not in (item.descricao_original or "").lower():
            continue
        if estado and item.status_revisao != estado:
            continue
        if natureza and item.natureza != natureza:
            continue
        visiveis.append(item)
    visiveis.sort(key=lambda item: _chave_ordem(item, ordem))

    item_id = request.GET.get("item") or ""
    selecionado = None
    if item_id.isdigit():
        selecionado = next((item for item in itens if str(item.pk) == item_id), None)
    filtros = {"q": busca, "estado": estado, "natureza": natureza, "ordem": ordem}
    revisados, total_revisoes = _progresso(plano, itens, metas)
    extraido = plano.valor_extraido
    cronograma = _cronograma(plano)
    return {
        "secao_plano": secao,
        "abas_plano": [
            {
                "codigo": codigo,
                "rotulo": rotulo,
                "ativa": codigo == secao,
                "url": _url(prestacao, plano, secao=codigo, **filtros),
            }
            for codigo, rotulo in ROTULOS_SECAO
        ],
        "filtros_plano": filtros,
        "itens_plano": [
            {
                "obj": item,
                "resumo": resumo_descricao(item.descricao),
                "url": _url(prestacao, plano, secao="despesas", item=item.pk, **filtros),
                "selecionado": selecionado is not None and item.pk == selecionado.pk,
                "rotulo": rotulo_revisao(item, "item", chaves),
                "elegivel_lote": avaliar_lote(item, chaves)[0],
                "motivo_lote": avaliar_lote(item, chaves)[1],
            }
            for item in visiveis
        ],
        "total_itens_plano": len(itens),
        "total_visivel_plano": len(visiveis),
        "soma_visivel_plano": _soma(item.valor_previsto for item in visiveis),
        "item_selecionado": selecionado,
        "proximo_pendente_url": _proximo_pendente(prestacao, plano, itens, selecionado, filtros),
        "metas_plano": [
            {
                "obj": meta,
                "parametros_limpos": parametros_legiveis(meta.parametros_afericao),
                "etapas_limpas": etapas_legiveis(meta.etapas, meta.parametros_afericao),
                "recorte": recorte_evidencia(meta.trecho, meta.descricao),
                "rotulo": rotulo_revisao(meta, "meta", chaves),
            }
            for meta in metas
        ],
        "evidencias_plano": _evidencias(plano),
        "progresso_revisado": revisados,
        "progresso_total": total_revisoes,
        "progresso_percentual": int(revisados * 100 / total_revisoes) if total_revisoes else 0,
        "revisao_concluida": total_revisoes > 0 and revisados == total_revisoes,
        "itens_pendentes": sum(1 for item in itens if item.status_revisao == StatusRevisaoPlano.AGUARDANDO),
        "itens_confirmados": sum(1 for item in itens if item.status_revisao == StatusRevisaoPlano.CONFIRMADO),
        "itens_corrigidos": sum(1 for item in itens if item.status_revisao == StatusRevisaoPlano.CORRIGIDO),
        "conciliacao_plano": _conciliacao(plano, extraido, cronograma["total"]),
        "cronograma_plano": cronograma,
        "pagina_pdf": (selecionado.pagina if selecionado and selecionado.pagina else 1),
        "mostrar_pdf": bool(plano.documento_id) and (secao == "documento" or (secao == "despesas" and selecionado)),
        "naturezas_plano": NaturezaItem.choices,
        "url_revisao_plano": reverse("prestacoes_contas:revisao_plano", kwargs={"pk": prestacao.pk, "plano_pk": plano.pk}),
        "url_itens_pendentes": _url(prestacao, plano, secao="despesas", estado=StatusRevisaoPlano.AGUARDANDO),
        "rotulo_item_selecionado": rotulo_revisao(selecionado, "item", chaves) if selecionado else "",
        "rotulo_plano": rotulo_revisao(plano, "identificacao", chaves),
        "rotulo_cronograma": rotulo_revisao(plano, "cronograma", chaves),
        "elegiveis_lote": sum(1 for item in visiveis if avaliar_lote(item, chaves)[0]),
        "bloqueados_lote": sum(1 for item in visiveis if not avaliar_lote(item, chaves)[0]),
    }


def url_workspace(prestacao, plano, dados, acao: str = "") -> str:
    secao = dados.get("retorno_secao") or dados.get("secao") or _secao_da_acao(acao)
    if secao not in SECOES:
        secao = "resumo"
    item = dados.get("item") or dados.get("item_id") or ""
    return _url(
        prestacao,
        plano,
        secao=secao,
        item=item,
        q=dados.get("q") or "",
        estado=dados.get("estado") or "",
        natureza=dados.get("natureza") or "",
        ordem=dados.get("ordem") or "",
    )


def _secao_da_acao(acao: str) -> str:
    if acao in {"confirmar_item", "corrigir_item", "rejeitar_item", "confirmar_itens_elegiveis"}:
        return "despesas"
    if acao in {"confirmar_meta", "corrigir_meta"}:
        return "metas"
    if acao in {"confirmar_cronograma", "corrigir_cronograma"}:
        return "cronograma"
    return "resumo"


def _url(prestacao, plano, **params) -> str:
    consulta = {"aba": "plano", "plano": plano.pk}
    for chave, valor in params.items():
        if valor not in ("", None):
            consulta[chave] = valor
    return reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}) + "?" + urlencode(consulta)


def _chave_ordem(item, ordem: str):
    if ordem == "valor":
        return (item.valor_previsto is None, -(item.valor_previsto or Decimal("0")), item.ordem)
    if ordem == "descricao":
        return ((item.descricao or "").lower(), item.ordem)
    if ordem == "estado":
        peso = {StatusRevisaoPlano.AGUARDANDO: 0, StatusRevisaoPlano.CORRIGIDO: 1, StatusRevisaoPlano.CONFIRMADO: 2}
        return (peso.get(item.status_revisao, 9), item.ordem)
    return (item.ordem, item.pk)


def _progresso(plano, itens, metas) -> tuple[int, int]:
    estados = [plano.status_revisao, plano.cronograma_status if plano.cronograma else StatusRevisaoPlano.CONFIRMADO]
    estados.extend(meta.status_revisao for meta in metas)
    estados.extend(item.status_revisao for item in itens)
    revisados = sum(1 for estado in estados if estado != StatusRevisaoPlano.AGUARDANDO)
    return revisados, len(estados)


def _proximo_pendente(prestacao, plano, itens, selecionado, filtros) -> str:
    pendentes = [item for item in itens if item.status_revisao == StatusRevisaoPlano.AGUARDANDO]
    if not pendentes:
        return ""
    if selecionado is None:
        escolhido = pendentes[0]
    else:
        posteriores = [item for item in pendentes if item.ordem > selecionado.ordem]
        escolhido = posteriores[0] if posteriores else pendentes[0]
        if escolhido.pk == selecionado.pk and len(pendentes) == 1:
            return ""
    return _url(prestacao, plano, secao="despesas", item=escolhido.pk, **filtros)


def _conciliacao(plano, extraido, cronograma_total) -> dict:
    global_informado = plano.valor_global
    return {
        "itens_fecham": extraido is not None and global_informado is not None and extraido == global_informado,
        "cronograma_fecha": cronograma_total is not None and global_informado is not None and cronograma_total == global_informado,
        "tem_global": global_informado is not None,
        "cronograma_total": cronograma_total,
    }


def _cronograma(plano) -> dict:
    linhas = []
    for linha in plano.cronograma or []:
        repasse = _decimal(linha.get("repasse"))
        contrapartida = _decimal(linha.get("contrapartida"))
        linhas.append(
            {
                **linha,
                "repasse_decimal": repasse,
                "contrapartida_decimal": contrapartida,
                "recorte": recorte_evidencia(linha.get("trecho") or "", linha.get("mes") or "", 80),
            }
        )
    maior = max((linha["repasse_decimal"] or Decimal("0") for linha in linhas), default=Decimal("0"))
    anos = []
    for ano in _anos(linhas):
        do_ano = [linha for linha in linhas if linha.get("ano") == ano]
        barras = []
        for linha in do_ano:
            valor = linha["repasse_decimal"] or Decimal("0")
            if maior > 0 and valor > 0:
                altura = max(8, int(valor * 100 / maior))
            else:
                altura = 2
            principal, sufixo = rotulo_milhar(linha["repasse_decimal"])
            barras.append(
                {
                    "mes": linha.get("mes") or "",
                    "sigla": SIGLAS_MES.get((linha.get("mes") or "").lower(), (linha.get("mes") or "")[:3]),
                    "valor": linha["repasse_decimal"],
                    "com_valor": valor > 0,
                    "rotulo": principal,
                    "sufixo": sufixo,
                    "contrapartida": linha["contrapartida_decimal"],
                    "altura": altura,
                    "pagina": linha.get("pagina"),
                    "trecho": recorte_evidencia(linha.get("trecho") or "", linha.get("mes") or "", 80),
                }
            )
        total_ano = _soma(linha["repasse_decimal"] for linha in do_ano)
        anos.append(
            {
                "ano": ano,
                "total": total_ano,
                "com_desembolso": sum(1 for linha in do_ano if (linha["repasse_decimal"] or 0) > 0),
                "barras": barras,
            }
        )
    return {
        "anos": anos,
        "linhas": linhas,
        "total": _soma(linha["repasse_decimal"] for linha in linhas),
        "contrapartida": _soma(linha["contrapartida_decimal"] for linha in linhas),
        "com_desembolso": sum(1 for linha in linhas if (linha["repasse_decimal"] or 0) > 0),
    }


def _anos(linhas) -> list:
    anos = []
    for linha in linhas:
        ano = linha.get("ano")
        if ano not in anos:
            anos.append(ano)
    return anos


def _evidencias(plano) -> list[dict]:
    campos = (
        ("titulo", "Título", plano.titulo),
        ("objeto", "Objeto", plano.objeto),
        ("finalidade", "Finalidade", plano.finalidade),
        ("transferencia", "Transferência", plano.transferencia),
        ("proponente", "Proponente", plano.proponente),
        ("unidade_gestora", "Unidade gestora", plano.unidade_gestora),
        ("publico_alvo", "Público alvo", plano.publico_alvo),
        ("situacao_informada", "Situação no documento", plano.situacao_informada),
    )
    evidencias = plano.evidencias or {}
    saida = []
    for nome, rotulo, valor in campos:
        origem = evidencias.get(nome) or {}
        saida.append(
            {
                "nome": nome,
                "rotulo": rotulo,
                "valor": valor or "",
                "pagina": origem.get("pagina"),
                "recorte": recorte_evidencia(origem.get("trecho") or "", str(valor or "")),
            }
        )
    return saida


def _soma(valores) -> Decimal | None:
    total = Decimal("0")
    achou = False
    for valor in valores:
        if valor is None:
            continue
        total += valor
        achou = True
    return total if achou else None


def _decimal(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def rotulo_milhar(valor: Decimal | None) -> tuple[str, str]:
    """Resume o repasse para caber acima da coluna. O valor exato continua no título e na tabela."""

    if valor is None or valor <= 0:
        return "", ""
    if valor < Decimal("1000"):
        quantizado = valor.quantize(Decimal("0.01"))
        inteiro, centavos = f"{quantizado:.2f}".split(".")
        return f"{int(inteiro)},{centavos}", ""
    milhares = (valor / Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return str(int(milhares)), "mil"


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _apos_afericao(texto: str) -> str:
    for rotulo in ("Aferição", "Afericao"):
        posicao = texto.rfind(rotulo)
        if posicao >= 0:
            return texto[posicao + len(rotulo) :].strip(" .:-")
    return texto


def _dividir_frase_grudada(texto: str) -> tuple[str, str]:
    achados = list(re.finditer(r"\.(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])", texto or ""))
    if not achados:
        return texto, ""
    corte = achados[-1]
    return texto[: corte.end()].strip(), texto[corte.end() :].strip()
