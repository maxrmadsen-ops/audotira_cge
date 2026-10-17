"""Extração do plano de trabalho a partir do texto recuperado do PDF.

Os registros nascem aguardando revisão. Não alteram o valor definitivo da prestação.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from aplicacao.documentos.codificacao import decodificar_uso_privado, mapear_uso_privado

MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
_ITEM = re.compile(
    r"Material/Servi[cç]o/Obra\s*(?P<descricao>.*?)\s*"
    r"Classifica[cç][aã]o Or[cç]ament[aá]ria\s*(?P<classificacao>.*?)\s*"
    r"Tipo Despesa\s*(?P<tipo>.*?)\s*"
    r"Recurso\s*(?P<recurso>.*?)\s*"
    r"Unidade Medida\s*(?P<unidade>.*?)\s*"
    r"Quantidade\s*(?P<quantidade>[\d.]+,\d{2})\s+(?P<unitario>[\d.]+,\d{2})\s*"
    r"Valor Unit[aá]rio \(R\$\)\s*"
    r"Valor Total \(R\$\)\s+(?P<total>[\d.]+,\d{2})",
    re.DOTALL,
)
_MES = re.compile(
    r"(Janeiro|Fevereiro|Mar[cç]o|Abril|Maio|Junho|Julho|Agosto|Setembro|Outubro|Novembro|Dezembro)"
    r"\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})",
)
_ANO_CRONOGRAMA = re.compile(r"Ano\s*(20\d{2})")
_ROTULOS_RECURSO = (
    "Valor Global (R$)",
    "Contrapartida (%)",
    "Valor Repasse (R$)",
    "Valor Contrapartida (R$)",
    "Valor Contrapartida Financeira (R$)",
    "Valor Contrapartida Bens e Serviços (R$)",
)


_ROTULOS_SOLTOS = (
    "Data Início Execução",
    "Data Término Execução",
    "Data Inicio Execucao",
    "Data Termino Execucao",
    "Objetivo/Resultados Esperados",
    "Objetivo/Resultados",
    "Objeto/Finalidade",
    "Descrição da Realidade",
    "Descricao da Realidade",
    "Classificação Orçamentária",
    "Classificacao Orcamentaria",
    "Material/Serviço/Obra",
    "Material/Servico/Obra",
    "Valor Contrapartida Financeira (R$)",
    "Valor Contrapartida Bens e Serviços (R$)",
    "Valor Contrapartida (R$)",
    "Valor Unitário (R$)",
    "Valor Total (R$)",
    "Valor Global (R$)",
    "Valor Repasse (R$)",
    "Programa Transferência",
    "Instrumento Transferência",
    "Forma de Execução",
    "Parametros de Aferição",
    "Unidade Gestora",
    "Unidade Medida",
    "Público Alvo",
    "Tipo Despesa",
    "Data Início",
    "Data Fim",
    "Data Situação",
    "Quantidade",
    "Proponente",
    "Transferência",
    "Recurso",
    "Descrição",
    "Situação",
    "Título",
    "Gestão",
    "Agência",
    "Ano",
)


def separar_rotulos(texto: str) -> str:
    """Alguns PDFs colam o rótulo no valor. O espaço só entra depois de um rótulo conhecido."""

    if not texto:
        return ""
    for rotulo in sorted(_ROTULOS_SOLTOS, key=len, reverse=True):
        inicio = 0
        while True:
            posicao = texto.find(rotulo, inicio)
            if posicao < 0:
                break
            fim = posicao + len(rotulo)
            anterior = texto[posicao - 1] if posicao else ""
            seguinte = texto[fim] if fim < len(texto) else ""
            if anterior.isalpha() or not seguinte or seguinte.isspace() or not (seguinte.isupper() or seguinte.isdigit()):
                inicio = fim
                continue
            texto = texto[:fim] + " " + texto[fim:]
            inicio = fim + 1
    return texto


def extrair_plano(paginas: list[dict], caminho=None) -> dict:
    """Lê páginas já decodificadas. `caminho` refina os recursos pela posição visual."""

    textos = []
    for pagina in paginas:
        texto, _ = decodificar_uso_privado(pagina.get("texto_extraido") or "")
        textos.append({"numero_pagina": pagina["numero_pagina"], "texto": separar_rotulos(texto)})
    identificacao = _identificacao(textos)
    metas = _metas(textos)
    itens = _itens(textos)
    cronograma = _cronograma(textos)
    recursos = _recursos_por_posicao(caminho) if caminho else {}
    if not recursos:
        recursos = _recursos_por_ordem_visual(textos)
    return {
        "identificacao": identificacao,
        "recursos": recursos,
        "metas": metas,
        "itens": itens,
        "cronograma": cronograma,
    }


def dinheiro(valor: str) -> Decimal | None:
    bruto = (valor or "").strip().replace(" ", "")
    if not bruto:
        return None
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        return Decimal(bruto)
    except InvalidOperation:
        return None


def data_br(valor: str) -> date | None:
    achado = re.search(r"(\d{2})/(\d{2})/(\d{4})", valor or "")
    if not achado:
        return None
    dia, mes, ano = (int(achado.group(indice)) for indice in (1, 2, 3))
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def sugerir_natureza(descricao: str, tipo_despesa: str) -> str:
    """Sugestão para o auditor. O tipo impresso no documento permanece separado."""

    texto = _sem_acento(f"{descricao} {tipo_despesa}").lower()
    if any(termo in texto for termo in ("inss", "fgts", "irpf", "rescis", "ferias")):
        return "encargo"
    if "encargo" in texto and not any(termo in texto for termo in ("professor", "profission", "pedagog")):
        return "encargo"
    if any(termo in texto for termo in ("professor", "profission", "pedagog", "educacao", "musicoterap")):
        return "pessoal"
    if "material" in texto and "servico" not in texto:
        return "material"
    if "servico" in texto or "serviço" in (tipo_despesa or "").lower():
        return "servico"
    return "outro"


def _revisao_iniciada(plano) -> bool:
    from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano

    if plano.status_revisao != StatusRevisaoPlano.AGUARDANDO or plano.cronograma_status != StatusRevisaoPlano.AGUARDANDO:
        return True
    return (
        plano.itens.exclude(status_revisao=StatusRevisaoPlano.AGUARDANDO).exists()
        or plano.metas.exclude(status_revisao=StatusRevisaoPlano.AGUARDANDO).exists()
    )


def estruturar_plano(documento) -> None:
    from pathlib import Path

    from django.db import transaction

    from aplicacao.documentos.armazenamento import ler_arquivo
    from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
    from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, Meta, PlanoTrabalho

    paginas = [
        {"numero_pagina": pagina.numero_pagina, "texto_extraido": pagina.texto_extraido}
        for pagina in documento.paginas.order_by("numero_pagina")
    ]
    caminho = Path(ler_arquivo(documento.nome_armazenado))
    analise = extrair_plano(paginas, caminho)
    identificacao = analise["identificacao"]
    with transaction.atomic():
        plano = PlanoTrabalho.objects.filter(prestacao=documento.prestacao_contas, documento=documento).first()
        if plano is not None and _revisao_iniciada(plano):
            return
        if plano is None:
            versao = (documento.prestacao_contas.planos.order_by("-versao").values_list("versao", flat=True).first() or 0) + 1
            plano = PlanoTrabalho(
                prestacao=documento.prestacao_contas,
                versao=versao,
                documento=documento,
                instrumento=documento.prestacao_contas.instrumento_principal,
            )
        plano.titulo = (identificacao.get("titulo") or "Plano de trabalho")[:255]
        plano.objeto = identificacao.get("objeto") or ""
        plano.finalidade = identificacao.get("finalidade") or ""
        plano.transferencia = (identificacao.get("transferencia") or "")[:40]
        plano.proponente = (identificacao.get("proponente") or "")[:255]
        plano.unidade_gestora = (identificacao.get("unidade_gestora") or "")[:255]
        plano.publico_alvo = (identificacao.get("publico_alvo") or "")[:255]
        plano.situacao_informada = (identificacao.get("situacao") or "")[:80]
        plano.vigencia_inicio = data_br(identificacao.get("inicio_execucao") or "")
        plano.vigencia_fim = data_br(identificacao.get("fim_execucao") or "")
        recursos = analise["recursos"]
        plano.valor_global = recursos.get("valor_global")
        plano.valor_repasse = recursos.get("valor_repasse")
        plano.valor_contrapartida = recursos.get("valor_contrapartida")
        plano.status_revisao = StatusRevisaoPlano.AGUARDANDO
        plano.cronograma_status = StatusRevisaoPlano.AGUARDANDO
        plano.evidencias = identificacao.get("evidencias") or {}
        plano.cronograma = analise["cronograma"]
        plano.documento = documento
        plano.save()
        plano.itens.filter(status_revisao=StatusRevisaoPlano.AGUARDANDO, documento=documento).delete()
        plano.metas.filter(status_revisao=StatusRevisaoPlano.AGUARDANDO, documento=documento).delete()
        for ordem, item in enumerate(analise["itens"], start=1):
            ItemPlanoTrabalho.objects.create(
                plano=plano,
                documento=documento,
                categoria=(item["classificacao"] or "")[:120],
                descricao=item["descricao"],
                descricao_original=item["descricao"],
                quantidade=item["quantidade"],
                unidade=(item["unidade"] or "")[:40],
                valor_unitario=item["valor_unitario"],
                valor_previsto=item["valor_total"],
                classificacao_orcamentaria=(item["classificacao"] or "")[:160],
                tipo_despesa=(item["tipo_despesa"] or "")[:80],
                recurso=(item["recurso"] or "")[:80],
                natureza=item["natureza_sugerida"],
                ordem=ordem,
                pagina=item["pagina"],
                trecho=item["trecho"][:2000],
                status_revisao=StatusRevisaoPlano.AGUARDANDO,
                demonstracao=documento.demonstracao,
            )
        for meta in analise["metas"]:
            Meta.objects.create(
                plano=plano,
                documento=documento,
                codigo="",
                descricao=meta["descricao"],
                descricao_original=meta["descricao"],
                forma_execucao=meta.get("forma_execucao") or "",
                parametros_afericao=meta.get("parametros_afericao") or "",
                etapas=meta.get("etapas") or "",
                indicador=(meta.get("parametros_afericao") or "")[:255],
                periodo_inicio=data_br(meta.get("inicio") or ""),
                periodo_fim=data_br(meta.get("fim") or ""),
                pagina=meta["pagina"],
                trecho=meta["trecho"][:2000],
                status_revisao=StatusRevisaoPlano.AGUARDANDO,
                demonstracao=documento.demonstracao,
            )


def _identificacao(paginas: list[dict]) -> dict:
    texto = ""
    numero = None
    for pagina in paginas:
        if "Proponente" in pagina["texto"]:
            texto = pagina["texto"]
            numero = pagina["numero_pagina"]
            break
    if not texto:
        return {"evidencias": {}}
    campos = {
        "proponente": _entre(texto, "Proponente", "Transferência"),
        "transferencia": _entre(texto, "Transferência", "Programa Transferência"),
        "unidade_gestora": _entre(texto, "Unidade Gestora", "Gestão"),
        "titulo": _entre(texto, "Título", "Objeto/Finalidade"),
        "objeto": _entre(texto, "Objeto/Finalidade", "Objetivo/Resultados"),
        "finalidade": _entre(texto, "Objetivo/Resultados Esperados", "Descrição da Realidade")
        or _entre(texto, "Objetivo/Resultados", "Descrição da Realidade"),
        "publico_alvo": _entre(texto, "Público Alvo", "Capacidade Técnica"),
        "situacao": _entre(texto, "Situação", "Data Situação"),
    }
    datas = re.search(
        r"Data In[ií]cio Execu[cç][aã]o\s*Data T[eé]rmino Execu[cç][aã]o\s*(\d{2}/\d{2}/\d{4})\s*(\d{2}/\d{2}/\d{4})",
        texto,
    )
    if datas:
        campos["inicio_execucao"] = datas.group(1)
        campos["fim_execucao"] = datas.group(2)
    evidencias = {}
    for nome, valor in campos.items():
        if not valor:
            continue
        evidencias[nome] = {"valor": valor, "pagina": numero, "trecho": _trecho(texto, valor)}
    campos["evidencias"] = evidencias
    return campos


def _metas(paginas: list[dict]) -> list[dict]:
    saida = []
    for pagina in paginas:
        texto = pagina["texto"]
        if "Forma de Execução" not in texto or "Descrição" not in texto:
            continue
        descricao = _entre(texto, "Descrição", "Data Início")
        if not descricao or len(descricao) < 8:
            continue
        datas = re.search(r"Data In[ií]cio\s*(\d{2}/\d{2}/\d{4})\s*Data Fim\s*(\d{2}/\d{2}/\d{4})", texto)
        forma = _entre(texto, "Forma de Execução", "Parametros")
        parametros = _entre(texto, "Parametros  de Aferição", "Etapas") or _entre(texto, "Parametros de Aferição", "Etapas")
        etapas = ""
        marcador = re.search(r"Etapas\s*$", texto, re.M)
        if marcador:
            antes = texto[: marcador.start()]
            linhas = [linha.strip() for linha in antes.splitlines() if linha.strip()]
            if len(linhas) >= 2:
                etapas = " ".join(linhas[-2:])
        saida.append(
            {
                "descricao": descricao,
                "inicio": datas.group(1) if datas else "",
                "fim": datas.group(2) if datas else "",
                "forma_execucao": forma,
                "parametros_afericao": parametros,
                "etapas": etapas,
                "pagina": pagina["numero_pagina"],
                "trecho": _trecho(texto, descricao),
            }
        )
    return saida


def _itens(paginas: list[dict]) -> list[dict]:
    itens = []
    for pagina in paginas:
        for achado in _ITEM.finditer(pagina["texto"]):
            descricao = _limpar(achado.group("descricao"))
            tipo = _limpar(achado.group("tipo"))
            quantidade = dinheiro(achado.group("quantidade"))
            unitario = dinheiro(achado.group("unitario"))
            total = dinheiro(achado.group("total"))
            itens.append(
                {
                    "descricao": descricao,
                    "classificacao": _limpar(achado.group("classificacao")),
                    "tipo_despesa": tipo,
                    "recurso": _limpar(achado.group("recurso")),
                    "unidade": _limpar(achado.group("unidade")),
                    "quantidade": quantidade,
                    "valor_unitario": unitario,
                    "valor_total": total,
                    "natureza_sugerida": sugerir_natureza(descricao, tipo),
                    "pagina": pagina["numero_pagina"],
                    "trecho": _limpar(achado.group(0))[:500],
                }
            )
    return itens


def _cronograma(paginas: list[dict]) -> list[dict]:
    linhas = []
    for pagina in paginas:
        if "Cronograma" not in pagina["texto"]:
            continue
        texto = pagina["texto"]
        marcadores = [(achado.start(), int(achado.group(1))) for achado in _ANO_CRONOGRAMA.finditer(texto)]
        meses = list(_MES.finditer(texto))
        if not marcadores or not meses:
            continue
        for achado in meses:
            ano = _ano_que_precede(marcadores, achado.start())
            if ano is None:
                continue
            valor_repasse = dinheiro(achado.group(2))
            valor_contrapartida = dinheiro(achado.group(3))
            linhas.append(
                {
                    "ano": ano,
                    "mes": achado.group(1),
                    "repasse": "" if valor_repasse is None else str(valor_repasse),
                    "contrapartida": "" if valor_contrapartida is None else str(valor_contrapartida),
                    "pagina": pagina["numero_pagina"],
                    "trecho": _limpar(achado.group(0))[:180],
                }
            )
    return linhas


def atualizar_anos_cronograma(plano) -> int:
    """Regrava só o ano, quando a página confirma o mesmo mês e os mesmos valores."""

    documento = plano.documento
    if documento is None or not plano.cronograma:
        return 0
    paginas = []
    for pagina in documento.paginas.all():
        texto, _ = decodificar_uso_privado(pagina.texto_extraido or "")
        paginas.append({"numero_pagina": pagina.numero_pagina, "texto": separar_rotulos(texto)})
    relido = _cronograma(paginas)
    atual = [dict(linha) for linha in plano.cronograma]
    if len(relido) != len(atual):
        return 0
    alteracoes = 0
    for linha, origem in zip(atual, relido):
        if linha.get("mes") != origem.get("mes"):
            return 0
        if not _mesmo_dinheiro(linha.get("repasse"), origem.get("repasse")):
            return 0
        if not _mesmo_dinheiro(linha.get("contrapartida"), origem.get("contrapartida")):
            return 0
        if linha.get("ano") != origem.get("ano"):
            linha["ano"] = origem["ano"]
            alteracoes += 1
    if alteracoes:
        plano.cronograma = atual
        plano.save(update_fields=["cronograma", "atualizado_em"])
    return alteracoes


def _ano_que_precede(marcadores: list[tuple[int, int]], posicao: int) -> int | None:
    ano = None
    for inicio, valor in marcadores:
        if inicio < posicao:
            ano = valor
        else:
            break
    return ano


def _mesmo_dinheiro(atual, relido) -> bool:
    return dinheiro(str(atual or "")) == dinheiro(str(relido or ""))


def _recursos_por_posicao(caminho) -> dict:
    if not caminho:
        return {}
    try:
        from pypdf import PdfReader
    except Exception:
        return {}
    try:
        leitor = PdfReader(str(caminho))
    except Exception:
        return {}
    for pagina in leitor.pages:
        itens = []

        def visitar(texto, cm, tm, fontDict, fontSize):
            decodificado = mapear_uso_privado(texto or "")
            limpo = " ".join(decodificado.split())
            if limpo:
                itens.append((float(tm[5]), limpo))

        try:
            pagina.extract_text(visitor_text=visitar)
        except Exception:
            continue
        rotulos = [(y, texto) for y, texto in itens if texto in _ROTULOS_RECURSO]
        valores = [(y, texto) for y, texto in itens if re.fullmatch(r"[\d.]+,\d{2}", texto)]
        if len(rotulos) < 4 or len(valores) < len(rotulos):
            continue
        rotulos.sort()
        valores.sort()
        pares = dict(zip((rotulo for _, rotulo in rotulos), (valor for _, valor in valores[: len(rotulos)])))
        return {
            "valor_global": dinheiro(pares.get("Valor Global (R$)") or ""),
            "valor_repasse": dinheiro(pares.get("Valor Repasse (R$)") or ""),
            "valor_contrapartida": dinheiro(pares.get("Valor Contrapartida (R$)") or ""),
            "contrapartida_percentual": dinheiro(pares.get("Contrapartida (%)") or ""),
            "contrapartida_financeira": dinheiro(pares.get("Valor Contrapartida Financeira (R$)") or ""),
            "contrapartida_bens": dinheiro(pares.get("Valor Contrapartida Bens e Serviços (R$)") or ""),
        }
    return {}


def _recursos_por_ordem_visual(paginas: list[dict]) -> dict:
    return {}


def _entre(texto: str, inicio: str, fim: str) -> str:
    padrao = re.compile(re.escape(inicio) + r"\s*(.*?)\s*(?=" + re.escape(fim) + r")", re.DOTALL)
    achado = padrao.search(texto or "")
    if not achado:
        return ""
    return _limpar(achado.group(1))


def _trecho(texto: str, valor: str) -> str:
    if not valor:
        return ""
    posicao = texto.find(valor[:40])
    if posicao < 0:
        return valor[:240]
    return " ".join(texto[max(0, posicao - 30) : posicao + len(valor[:80]) + 40].split())[:240]


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _sem_acento(texto: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(caractere for caractere in base if not unicodedata.combining(caractere))
