"""Validação da cláusula de objeto e finalidade. Não altera os atributos técnicos."""

from types import SimpleNamespace

from django.utils import timezone

from aplicacao.instrumentos.escolhas import CategoriaClausula, StatusCampo
from aplicacao.instrumentos.models import CampoInstrumento, TermoCongelado, TermoFomento

NOME_UNIDADE = "unidade_objeto_finalidade"
ATRIBUTOS = frozenset({"objeto", "finalidade", "destinacao"})
TITULO_GRUPO = "Objeto e finalidade"
STATUS_REVISAO_HUMANA = {
    StatusCampo.VALIDADO,
    StatusCampo.CORRIGIDO,
    StatusCampo.NAO_IDENTIFICADO,
    StatusCampo.REJEITADO,
}
STATUS_PENDENTE = {StatusCampo.EXTRAIDO, StatusCampo.AGUARDANDO}
ROTULO_SITUACAO = {
    StatusCampo.VALIDADO: "Validada",
    StatusCampo.CORRIGIDO: "Corrigida",
    StatusCampo.REJEITADO: "Divergente",
    StatusCampo.AGUARDANDO: "Pendente",
    StatusCampo.EXTRAIDO: "Pendente",
}


def clausula_do_objeto(termo: TermoFomento):
    clausulas = list(termo.clausulas.all())
    for clausula in clausulas:
        if clausula.categoria == CategoriaClausula.OBJETO:
            return clausula
    for clausula in clausulas:
        base = f"{clausula.titulo} {clausula.texto}".lower()
        if "objeto" in base or "finalidade" in base:
            return clausula
    for clausula in clausulas:
        if (clausula.ordinal or "").upper() == "PRIMEIRA":
            return clausula
    return None


def texto_integral(clausula) -> str:
    if clausula is None:
        return ""
    titulo = " ".join(parte for parte in ("CLÁUSULA", clausula.ordinal, clausula.titulo) if parte).strip()
    corpo = clausula.texto or ""
    if titulo and corpo:
        return f"{titulo}\n{corpo}"
    return titulo or corpo


def registro_unidade(termo: TermoFomento):
    return termo.campos.filter(nome=NOME_UNIDADE).first()


def _humanas(atributos: list) -> list:
    return [campo for campo in atributos if campo.validado_por_id and campo.status in STATUS_REVISAO_HUMANA]


def ha_conflito(atributos: list) -> bool:
    return len({campo.status for campo in _humanas(atributos)}) > 1


def _alertas(termo, atributos: list) -> list[str]:
    from aplicacao.instrumentos.conferencia import alerta_do_campo

    achados = []
    for campo in atributos:
        alerta = alerta_do_campo(termo, campo)
        if alerta:
            achados.append(alerta)
    return achados


def motivos_bloqueio_lote(termo, atributos: list, texto: str, unidade) -> list[str]:
    if unidade and unidade.validado_por_id:
        return []
    if not (texto or "").strip():
        return ["A cláusula não foi localizada. Nenhum texto será completado por inferência."]
    motivos = []
    if _alertas(termo, atributos):
        motivos.append(
            "Há suspeita de truncamento ou inconsistência em atributo técnico. A confirmação em lote não inclui esta unidade."
        )
    if ha_conflito(atributos):
        motivos.append(
            "Decisões anteriores dos atributos são conflitantes. Elas foram preservadas e a unidade continua pendente até revisão individual."
        )
    elif _humanas(atributos):
        motivos.append(
            "Há validação humana anterior nos atributos. Ela foi preservada e não migra para esta unidade."
        )
    if any(campo.status == StatusCampo.CORRIGIDO for campo in atributos):
        motivos.append("Há correção anterior em atributo técnico. A confirmação em lote não a substitui.")
    return motivos


def unidade_elegivel_lote(termo: TermoFomento) -> bool:
    if termo.congelado:
        return False
    clausula = clausula_do_objeto(termo)
    texto = texto_integral(clausula)
    atributos = [campo for campo in termo.campos.all() if campo.nome in ATRIBUTOS]
    unidade = registro_unidade(termo)
    if unidade and unidade.validado_por_id:
        return False
    return not motivos_bloqueio_lote(termo, atributos, texto, unidade)


def montar_unidade(termo: TermoFomento, atributos: list) -> dict:
    clausula = clausula_do_objeto(termo)
    texto = texto_integral(clausula)
    unidade = registro_unidade(termo)
    alertas = _alertas(termo, atributos)
    conflito = ha_conflito(atributos)
    motivos = motivos_bloqueio_lote(termo, atributos, texto, unidade)
    if unidade and unidade.validado_por_id:
        situacao = ROTULO_SITUACAO.get(unidade.status, unidade.get_status_display())
    elif alertas or conflito:
        situacao = "Divergente"
    else:
        situacao = "Pendente"
    if situacao == "Validada" and not alertas:
        classe, icone = "grupo-conferido", "✓"
    elif situacao == "Corrigida" and not alertas:
        classe, icone = "grupo-conferido", "✓"
    elif situacao == "Pendente":
        classe, icone = "grupo-aguardando", "○"
    else:
        classe, icone = "grupo-divergencia", "!"
    revisada = bool(unidade and unidade.validado_por_id and unidade.status in {StatusCampo.VALIDADO, StatusCampo.CORRIGIDO, StatusCampo.REJEITADO})
    return {
        "nome": NOME_UNIDADE,
        "titulo": "Objeto e finalidade da parceria",
        "texto": texto,
        "pagina": clausula.pagina if clausula else None,
        "ordinal": clausula.ordinal if clausula else "",
        "titulo_clausula": clausula.titulo if clausula else "",
        "situacao": situacao,
        "classe": classe,
        "icone": icone,
        "motivos": motivos,
        "elegivel": unidade_elegivel_lote(termo) if not motivos else False,
        "revisada": revisada,
        "pendente": not revisada,
        "registro": unidade,
        "conflito": conflito,
        "alertas": alertas,
        "ressalva": "Atributo técnico inconsistente ou ausente. A confirmação da cláusula não o valida." if alertas else "",
    }


def aplicar_unidade(grupo: dict, termo: TermoFomento) -> dict:
    if grupo["titulo"] != TITULO_GRUPO:
        grupo["consolidada"] = False
        return grupo
    unidade = montar_unidade(termo, grupo["campos"])
    grupo["consolidada"] = True
    grupo["unidade"] = unidade
    grupo["ancora"] = "objeto-e-finalidade"
    grupo["situacao"] = unidade["situacao"]
    grupo["classe"] = unidade["classe"]
    grupo["icone"] = unidade["icone"]
    grupo["quantidade"] = 1
    grupo["revisados"] = 1 if unidade["revisada"] else 0
    grupo["pendentes"] = 1 if unidade["pendente"] else 0
    grupo["elegiveis"] = []
    if unidade["elegivel"]:
        grupo["elegiveis"] = [
            SimpleNamespace(nome=NOME_UNIDADE, rotulo=unidade["titulo"], valor_extraido=unidade["texto"])
        ]
    grupo["preservados"] = 0 if unidade["elegivel"] else 1
    return grupo


def confirmar_unidade(termo: TermoFomento, usuario, modalidade: str = "individual"):
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    clausula = clausula_do_objeto(termo)
    texto = texto_integral(clausula)
    if not texto.strip():
        raise ValueError("A cláusula não foi localizada. Nenhum texto será inventado.")
    return _gravar(termo, clausula, usuario, texto, texto, StatusCampo.VALIDADO, "", modalidade)


def corrigir_unidade(termo: TermoFomento, usuario, valor: str, observacao: str):
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    clausula = clausula_do_objeto(termo)
    texto = texto_integral(clausula)
    valor = (valor or "").strip()
    if not valor:
        raise ValueError("Informe o texto validado da cláusula.")
    if valor != texto.strip() and not (observacao or "").strip():
        raise ValueError("A correção da cláusula exige justificativa. O texto extraído permanece.")
    return _gravar(termo, clausula, usuario, texto, valor, StatusCampo.CORRIGIDO if valor != texto.strip() else StatusCampo.VALIDADO, observacao, "individual")


def divergir_unidade(termo: TermoFomento, usuario, observacao: str):
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    if not (observacao or "").strip():
        raise ValueError("O registro de divergência exige justificativa.")
    clausula = clausula_do_objeto(termo)
    texto = texto_integral(clausula)
    return _gravar(termo, clausula, usuario, texto, "", StatusCampo.REJEITADO, observacao, "individual")


def _gravar(termo, clausula, usuario, texto, validado, status, observacao, modalidade):
    campo = registro_unidade(termo)
    if campo is None:
        campo = CampoInstrumento(termo=termo, nome=NOME_UNIDADE, rotulo="Objeto e finalidade da parceria", metodo="clausula")
    if not (campo.valor_extraido or "").strip():
        campo.valor_extraido = texto
    campo.valor_validado = validado
    campo.status = status
    campo.observacao = (observacao or "").strip()
    campo.validado_por = usuario
    campo.validado_em = timezone.now()
    campo.pagina = clausula.pagina if clausula else campo.pagina
    campo.trecho = texto
    campo.save()
    campo.modalidade_gravada = modalidade
    campo.clausula_rotulo = " ".join(parte for parte in (getattr(clausula, "ordinal", ""), getattr(clausula, "titulo", "")) if parte)
    return campo


def progresso_da_conferencia(termo: TermoFomento | None) -> dict:
    from aplicacao.instrumentos.preparacao import resumo_validacao

    bruto = resumo_validacao(termo)
    if termo is None:
        bruto.update(total=0, revisados=0, conferidos=0, percentual=0, atributos=0, atributos_ausentes=0, pendentes_unidade=0)
        return bruto
    from aplicacao.instrumentos.esquema_partes import CAMPOS_AGREGADOS, PREFIXO_ATRIBUTO, montar_unidades
    from aplicacao.instrumentos.unidade_identificacao import (
        CAMPOS_FONTE,
        NOME_UNIDADE as NOME_IDENTIFICACAO,
        PREFIXO,
        montar_identificacao,
    )

    campos = list(termo.campos.all())
    por_nome = {campo.nome: campo for campo in campos}
    unidades_parte = montar_unidades(termo, por_nome)
    identificacao = montar_identificacao(termo, por_nome)
    tecnicos = [campo for campo in campos if campo.nome in ATRIBUTOS]
    unidade = next((campo for campo in campos if campo.nome == NOME_UNIDADE), None)

    def fora(nome: str) -> bool:
        if nome in ATRIBUTOS or nome == NOME_UNIDADE or nome.startswith(PREFIXO_ATRIBUTO):
            return True
        if nome in CAMPOS_FONTE or nome == NOME_IDENTIFICACAO or nome.startswith(PREFIXO):
            return True
        return bool(unidades_parte) and nome in CAMPOS_AGREGADOS

    demais = [campo for campo in campos if not fora(campo.nome)]
    revisados = sum(1 for campo in demais if campo.status in {StatusCampo.VALIDADO, StatusCampo.CORRIGIDO})
    pendentes = sum(1 for campo in demais if campo.status in STATUS_PENDENTE)
    nao_identificadas = sum(1 for campo in demais if campo.status == StatusCampo.NAO_IDENTIFICADO)
    corrigidas = sum(1 for campo in demais if campo.status == StatusCampo.CORRIGIDO)
    revisadas_parte = [item for item in unidades_parte if item["revisada"]]
    corrigidas += sum(1 for item in revisadas_parte if any(linha["situacao"] == "Corrigida pelo auditor" for linha in item["linhas"]))
    revisados += len(revisadas_parte)
    pendentes += len(unidades_parte) - len(revisadas_parte)
    if identificacao["revisada"]:
        revisados += 1
        if identificacao["corrigida"]:
            corrigidas += 1
    else:
        pendentes += 1
    if unidade and unidade.validado_por_id and unidade.status in {StatusCampo.VALIDADO, StatusCampo.CORRIGIDO}:
        revisados += 1
        if unidade.status == StatusCampo.CORRIGIDO:
            corrigidas += 1
    elif unidade and unidade.validado_por_id and unidade.status == StatusCampo.REJEITADO:
        revisados += 1
    else:
        pendentes += 1
    total = len(demais) + 1 + len(unidades_parte) + 1
    percentual = round(100 * revisados / total) if total else 0
    confirmadas_parte = sum(
        1
        for item in revisadas_parte
        if not any(linha["situacao"] == "Corrigida pelo auditor" for linha in item["linhas"])
    )
    bruto.update(
        confirmadas=sum(1 for campo in demais if campo.status == StatusCampo.VALIDADO)
        + (1 if unidade and unidade.status == StatusCampo.VALIDADO else 0)
        + confirmadas_parte
        + (1 if identificacao["revisada"] and not identificacao["corrigida"] else 0),
        corrigidas=corrigidas,
        nao_identificadas=nao_identificadas,
        pendentes=pendentes,
        total=total,
        revisados=revisados,
        conferidos=revisados,
        percentual=percentual,
        atributos=len(tecnicos),
        atributos_ausentes=sum(1 for campo in tecnicos if campo.status == StatusCampo.NAO_IDENTIFICADO or not (campo.valor_extraido or "").strip()),
    )
    return bruto
