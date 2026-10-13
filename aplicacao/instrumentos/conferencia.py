"""Apresentação e confirmação em lote do Passo 1. Não extrai nem classifica."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.db import transaction

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.ficha import GRUPOS_CAMPOS
from aplicacao.instrumentos.escolhas import StatusCampo
from aplicacao.instrumentos.models import CampoInstrumento, TermoCongelado, TermoFomento
from aplicacao.instrumentos.servico import confirmar_campo
from aplicacao.instrumentos.esquema_partes import CAMPOS_AGREGADOS, PREFIXO_ATRIBUTO, aplicar_partes
from aplicacao.instrumentos.unidade_identificacao import CAMPOS_FONTE, NOME_UNIDADE as NOME_IDENTIFICACAO, PREFIXO, aplicar_identificacao
from aplicacao.instrumentos.unidade_objeto import ATRIBUTOS, NOME_UNIDADE, TITULO_GRUPO, aplicar_unidade

CAMPOS_ARITMETICOS = {"valor_total", "parcelas"}
STATUS_PENDENTE = {StatusCampo.EXTRAIDO, StatusCampo.AGUARDANDO}
STATUS_REVISADO = {StatusCampo.VALIDADO, StatusCampo.CORRIGIDO}
TITULOS_OPERACIONAIS = {titulo for titulo, _nomes in GRUPOS_CAMPOS}
ROTULOS_MODALIDADE = {
    "individual": "Individual",
    "lote_grupo": "Lote do grupo",
    "lote_instrumento": "Lote do instrumento",
}
FILTROS_CONFERENCIA = {"revisados", "pendentes", "ausentes", "divergentes"}
DINHEIRO_COMPLETO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})")
DINHEIRO_INCOMPLETO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*)(?!\d)(?!\s*,\d{2})(?!\.\d)")


def _decimal_brasileiro(token: str):
    try:
        return Decimal(token.replace(".", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def alerta_do_campo(termo: TermoFomento, campo: CampoInstrumento) -> str:
    """Sinaliza truncamento ou divergência monetária. Não altera o valor gravado."""
    texto = campo.valor_extraido or ""
    incompletos = DINHEIRO_INCOMPLETO.findall(texto)
    if incompletos and campo.nome not in CAMPOS_ARITMETICOS:
        relacionado = _referencia_valor_total(termo)
        return (
            "Valor monetário possivelmente truncado: o ponto de milhar pode ter sido lido como fim de frase. "
            "Confira a origem. Nenhum valor de outro campo será copiado."
            + relacionado
        )
    if campo.nome == "destinacao" and termo.valor_total is not None:
        for token in DINHEIRO_COMPLETO.findall(texto):
            valor = _decimal_brasileiro(token)
            if valor is not None and valor != termo.valor_total:
                return (
                    "O valor monetário da destinação difere do valor total extraído. "
                    "Confira a origem. O valor total não será copiado para este campo."
                    + _referencia_valor_total(termo)
                )
    return ""


def _referencia_valor_total(termo: TermoFomento) -> str:
    if (termo.valor_total_texto or "").strip():
        return f" Campo relacionado: Valor total (R$ {termo.valor_total_texto})."
    if termo.valor_total is not None:
        return f" Campo relacionado: Valor total ({termo.valor_total})."
    return ""


def _inconsistencia_pendente_relacionada(termo: TermoFomento, campo: CampoInstrumento) -> str:
    if campo.nome != "valor_total":
        return ""
    relacionados = []
    for outro in termo.campos.all():
        if outro.pk == campo.pk or outro.status not in STATUS_PENDENTE:
            continue
        if alerta_do_campo(termo, outro):
            relacionados.append(outro.rotulo)
    if not relacionados:
        return ""
    nomes = ", ".join(relacionados)
    return (
        f"Este valor está relacionado a {nomes}, com possível truncamento ou divergência. "
        "A confirmação em lote não inclui este campo. A conferência individual continua disponível."
    )


def campo_elegivel_lote(campo: CampoInstrumento, termo: TermoFomento) -> bool:
    if campo.nome in ATRIBUTOS or campo.nome == NOME_UNIDADE or campo.nome in CAMPOS_AGREGADOS or campo.nome.startswith(PREFIXO_ATRIBUTO):
        return False
    if campo.nome in CAMPOS_FONTE or campo.nome == NOME_IDENTIFICACAO or campo.nome.startswith(PREFIXO):
        return False
    if campo.status not in STATUS_PENDENTE:
        return False
    if not (campo.valor_extraido or "").strip():
        return False
    if divergencia_aritmetica(termo, campo.nome):
        return False
    if alerta_do_campo(termo, campo):
        return False
    if _inconsistencia_pendente_relacionada(termo, campo):
        return False
    return True


def divergencia_aritmetica(termo: TermoFomento, nome: str) -> bool:
    if nome not in CAMPOS_ARITMETICOS:
        return False
    if (termo.alerta_aritmetico or "").strip():
        return True
    return termo.consistente_aritmeticamente is False


def confirmar_lote(termo: TermoFomento, usuario, nomes=None) -> list[CampoInstrumento]:
    """Confirma só campos identificados, pendentes e sem divergência. Não grava por cima dos demais."""
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    with transaction.atomic():
        bloqueado = TermoFomento.objects.select_for_update().get(pk=termo.pk)
        if bloqueado.congelado:
            raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
        consulta = CampoInstrumento.objects.select_for_update().filter(termo=bloqueado)
        if nomes is not None:
            consulta = consulta.filter(nome__in=list(nomes))
        confirmados = []
        for campo in consulta.order_by("nome"):
            campo.termo = bloqueado
            if not campo_elegivel_lote(campo, bloqueado):
                continue
            confirmar_campo(campo, usuario)
            confirmados.append(campo)
        return confirmados


def progresso(resumo: dict) -> dict:
    total = resumo["confirmadas"] + resumo["corrigidas"] + resumo["nao_identificadas"] + resumo["pendentes"]
    revisados = resumo["confirmadas"] + resumo["corrigidas"]
    percentual = round(100 * revisados / total) if total else 0
    return {
        **resumo,
        "total": total,
        "revisados": revisados,
        "conferidos": revisados,
        "percentual": percentual,
    }


def modalidades_por_campo(prestacao_id) -> dict[str, str]:
    registros = RegistroAuditoria.objects.filter(
        evento__in=(
            RegistroAuditoria.Evento.CAMPO_CONFIRMADO,
            RegistroAuditoria.Evento.CAMPO_CORRIGIDO,
            RegistroAuditoria.Evento.CAMPO_NAO_IDENTIFICADO,
        ),
        detalhes__prestacao=prestacao_id,
    ).order_by("id")
    mapa = {}
    for registro in registros:
        detalhes = registro.detalhes if isinstance(registro.detalhes, dict) else {}
        nome = detalhes.get("campo")
        if nome:
            mapa[nome] = detalhes.get("modalidade") or "individual"
    return mapa


def montar_grupos(termo: TermoFomento, modalidades: dict | None = None) -> list[dict]:
    modalidades = modalidades or {}
    por_nome = {campo.nome: campo for campo in termo.campos.all()}
    usados = set()
    grupos = []
    for titulo, nomes in GRUPOS_CAMPOS:
        itens = [por_nome[nome] for nome in nomes if nome in por_nome]
        usados.update(nomes)
        grupo = _grupo(titulo, itens, termo, modalidades)
        if titulo == "Identificação do instrumento":
            grupo = aplicar_identificacao(grupo, termo, por_nome)
        if titulo == "Partes envolvidas":
            grupo = aplicar_partes(grupo, termo, por_nome)
        if titulo == TITULO_GRUPO:
            grupo = aplicar_unidade(grupo, termo)
        grupos.append(grupo)
    outros = [
        campo
        for nome, campo in por_nome.items()
        if nome not in usados and nome != NOME_UNIDADE and nome != NOME_IDENTIFICACAO and not nome.startswith(PREFIXO_ATRIBUTO) and not nome.startswith(PREFIXO)
    ]
    if outros:
        grupos.append(_grupo("Outros dados extraídos", outros, termo, modalidades))
    return grupos


def elegiveis_instrumento(grupos: list[dict]) -> list[CampoInstrumento]:
    vistos = []
    for grupo in grupos:
        vistos.extend(grupo["elegiveis"])
    return vistos


def secoes_complementares(ficha: dict | None) -> list[dict]:
    if not ficha:
        return []
    secoes = []
    for grupo in ficha.get("grupos") or []:
        titulo = grupo["titulo"]
        if titulo in TITULOS_OPERACIONAIS or titulo == "Outros dados extraídos":
            extras = [linha for linha in grupo["linhas"] if not linha.get("campo_id")]
            if extras:
                secoes.append({"titulo": f"Detalhes de {titulo[:1].lower()}{titulo[1:]}", "linhas": extras})
            continue
        secoes.append(grupo)
    return secoes


def _grupo(titulo: str, campos: list[CampoInstrumento], termo: TermoFomento, modalidades: dict) -> dict:
    for campo in campos:
        campo.alerta_integridade = alerta_do_campo(termo, campo)
        campo.alerta_relacionado = _inconsistencia_pendente_relacionada(termo, campo)
        campo.elegivel_lote = campo_elegivel_lote(campo, termo)
        campo.divergente = bool(campo.alerta_integridade or campo.alerta_relacionado) or divergencia_aritmetica(termo, campo.nome)
        campo.pode_confirmar = (
            campo.status in STATUS_PENDENTE
            and bool((campo.valor_extraido or "").strip())
            and not campo.alerta_integridade
        )
        codigo = modalidades.get(campo.nome, "")
        campo.modalidade_exibicao = ROTULOS_MODALIDADE.get(codigo, "")
    elegiveis = [campo for campo in campos if campo.elegivel_lote]
    revisados = sum(1 for campo in campos if campo.status in STATUS_REVISADO)
    pendentes = sum(1 for campo in campos if campo.status in STATUS_PENDENTE)
    ausentes = sum(1 for campo in campos if campo.status == StatusCampo.NAO_IDENTIFICADO)
    reconhecidas = sum(1 for campo in campos if _ausencia_reconhecida(campo))
    tratados = revisados + reconhecidas
    divergencias_abertas = sum(1 for campo in campos if campo.divergente and campo.status in STATUS_PENDENTE)
    if not campos:
        situacao, classe, icone = "Sem campos", "grupo-aguardando", "–"
    elif divergencias_abertas:
        situacao, classe, icone = "Divergência", "grupo-divergencia", "!"
    elif tratados == len(campos):
        situacao, classe, icone = "Conferido", "grupo-conferido", "✓"
    elif tratados:
        situacao, classe, icone = "Em conferência", "grupo-parcial", "◔"
    else:
        situacao, classe, icone = "Aguardando conferência", "grupo-aguardando", "○"
    return {
        "titulo": titulo,
        "campos": campos,
        "elegiveis": elegiveis,
        "quantidade": len(campos),
        "revisados": revisados,
        "pendentes": pendentes,
        "ausentes": ausentes,
        "preservados": len(campos) - len(elegiveis),
        "situacao": situacao,
        "classe": classe,
        "icone": icone,
        "percentual": round(100 * tratados / len(campos)) if campos else 0,
        "ancora": ancora_grupo(titulo),
        "consolidada": False,
        "unidade": None,
    }


def _ausencia_reconhecida(campo: CampoInstrumento) -> bool:
    return campo.status == StatusCampo.NAO_IDENTIFICADO and bool(campo.validado_por_id)


def ancora_grupo(titulo: str) -> str:
    texto = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "grupo"


def contagem_divergencias(grupos: list[dict]) -> int:
    return sum(1 for grupo in grupos for campo in grupo["campos"] if campo.divergente)


def parametro_volta(nome: str, valor: str) -> str:
    texto = (valor or "").strip()
    if nome == "filtro":
        return texto if texto in FILTROS_CONFERENCIA else ""
    if nome == "campo" and re.fullmatch(r"[a-z0-9_]{1,80}", texto):
        return texto
    if nome == "grupo" and re.fullmatch(r"[a-z0-9-]{1,80}", texto):
        return texto
    return ""


def ler_volta(request) -> dict:
    return {
        "grupo_aberto": parametro_volta("grupo", request.GET.get("grupo", "")),
        "campo_foco": parametro_volta("campo", request.GET.get("campo", "")),
        "filtro_ativo": parametro_volta("filtro", request.GET.get("filtro", "")) or "todos",
    }


def destino_conferencia(base: str, origem) -> str:
    dados = origem.POST if hasattr(origem, "POST") else origem
    params = {}
    for nome in ("grupo", "campo", "filtro"):
        limpo = parametro_volta(nome, dados.get(nome) or "")
        if limpo:
            params[nome] = limpo
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def navegacao_processo(
    atividade_atual: str,
    estado_instrumento: str,
    url_instrumento: str,
    url_base: str = "",
    base_disponivel: bool = False,
) -> list[dict]:
    instrumento_atual = atividade_atual == "instrumento"
    base_atual = atividade_atual == "base"
    futuras = ("Não iniciado", False, False, "")
    def atividade(nome, estado, atual, disponivel, url):
        return {"nome": nome, "estado": estado, "atual": atual, "disponivel": disponivel, "url": url}
    def futuras_de(nomes):
        return [atividade(nome, *futuras) for nome in nomes]
    if base_atual:
        estado_base = "Etapa atual"
    elif base_disponivel:
        estado_base = "Disponível"
    else:
        estado_base = "Não iniciado"
    return [
        {
            "titulo": "Preparação da análise",
            "numero": 1,
            "atual": True,
            "atividades": [
                atividade("Instrumento da Parceria", estado_instrumento, instrumento_atual, True, url_instrumento),
                atividade("Base Normativa", estado_base, base_atual, base_disponivel, url_base),
                *futuras_de(("Entidade", "Plano de Trabalho")),
            ],
        },
        {
            "titulo": "Acompanhamento e análise das prestações",
            "numero": 2,
            "atual": False,
            "atividades": futuras_de((
                "Prestações parciais",
                "Documentos comprobatórios",
                "Verificações",
                "Achados",
                "Diligências",
            )),
        },
        {
            "titulo": "Encerramento e parecer final",
            "numero": 3,
            "atual": False,
            "atividades": futuras_de((
                "Prestação final",
                "Consolidação das análises",
                "Pendências",
                "Parecer",
                "Conclusão administrativa",
            )),
        },
    ]
