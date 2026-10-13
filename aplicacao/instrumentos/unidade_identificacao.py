"""Unidade de identificação do instrumento. Não inventa atributo e não chama modelo sozinha."""

from django.utils import timezone

from aplicacao.instrumentos.escolhas import PapelParte, StatusCampo
from aplicacao.instrumentos.models import CampoInstrumento, TermoCongelado

NOME_UNIDADE = "unidade_identificacao"
PREFIXO = "idinst_"
CAMPOS_FONTE = frozenset({"identificacao", "processo", "municipio"})
CATALOGO = (
    ("tipo", "Tipo de instrumento", "identificacao"),
    ("numero", "Número do instrumento", "identificacao"),
    ("processo", "Número do processo administrativo", "processo"),
    ("municipio", "Município da entidade convenente", "municipio"),
)
STATUS_HUMANO = {
    StatusCampo.VALIDADO,
    StatusCampo.CORRIGIDO,
    StatusCampo.NAO_IDENTIFICADO,
    StatusCampo.REJEITADO,
}


def nome_atributo(chave: str) -> str:
    return f"{PREFIXO}{chave}"


def _texto(valor) -> str:
    return " ".join(str(valor or "").split())


def _municipio_convenente(termo) -> str:
    parte = termo.partes.filter(papel=PapelParte.BENEFICIARIO).first()
    municipio = _texto(parte.municipio if parte is not None and parte.municipio else termo.municipio)
    uf = _texto(parte.uf if parte is not None and parte.uf else termo.uf)
    if municipio and uf:
        return f"{municipio}/{uf}"
    return municipio or uf


def _numero(termo) -> str:
    numero = _texto(termo.numero)
    if numero and termo.ano:
        return f"{numero}/{termo.ano}"
    return numero


def valor_atributo(termo, chave: str) -> str:
    if chave == "tipo":
        return _texto(termo.tipo_instrumento)
    if chave == "numero":
        return _numero(termo)
    if chave == "processo":
        return _texto(termo.processo_sgpe)
    if chave == "municipio":
        return _municipio_convenente(termo)
    return ""


def listar_atributos(termo, campos_por_nome: dict) -> list[dict]:
    linhas = []
    for chave, rotulo, fonte in CATALOGO:
        extraido = valor_atributo(termo, chave)
        campo = campos_por_nome.get(nome_atributo(chave))
        origem = campos_por_nome.get(fonte)
        humano = bool(campo and campo.validado_por_id and campo.status in STATUS_HUMANO)
        if humano and campo.status == StatusCampo.CORRIGIDO:
            situacao = "Corrigida pelo auditor"
        elif humano and campo.status == StatusCampo.VALIDADO:
            situacao = "Validada"
        elif not extraido:
            situacao = "Não identificado no documento"
        else:
            situacao = "Pendente"
        linhas.append(
            {
                "chave": chave,
                "nome": nome_atributo(chave),
                "rotulo": rotulo,
                "extraido": extraido,
                "exibicao": campo.valor_validado if humano and campo.valor_validado else extraido,
                "situacao": situacao,
                "elegivel": bool(extraido) and not humano,
                "pagina": origem.pagina if origem is not None else None,
                "trecho": (origem.trecho or "") if origem is not None else "",
                "metodo": (origem.metodo or termo.metodo_extracao or "") if origem is not None else (termo.metodo_extracao or ""),
                "campo": campo,
                "humano": humano,
            }
        )
    return linhas


def montar_identificacao(termo, campos_por_nome: dict) -> dict:
    linhas = listar_atributos(termo, campos_por_nome)
    elegiveis = [linha for linha in linhas if linha["elegivel"]]
    identificados = [linha for linha in linhas if linha["extraido"]]
    revisada = bool(identificados) and all(not linha["elegivel"] for linha in identificados)
    corrigida = revisada and any(linha["situacao"] == "Corrigida pelo auditor" for linha in linhas)
    evidencias = []
    vistos = set()
    for linha in linhas:
        marcador = (linha["pagina"], linha["trecho"])
        if marcador in vistos:
            continue
        vistos.add(marcador)
        evidencias.append(
            {
                "rotulos": [item["rotulo"] for item in linhas if (item["pagina"], item["trecho"]) == marcador],
                "pagina": linha["pagina"],
                "trecho": linha["trecho"],
                "metodo": linha["metodo"],
            }
        )
    return {
        "linhas": linhas,
        "elegiveis": elegiveis,
        "ausentes": [linha for linha in linhas if not linha["extraido"]],
        "identificados": identificados,
        "revisada": revisada,
        "corrigida": corrigida,
        "evidencias": evidencias,
        "versao": termo.versao,
    }


def aplicar_identificacao(grupo: dict, termo, campos_por_nome: dict) -> dict:
    unidade = montar_identificacao(termo, campos_por_nome)
    grupo["tipo"] = "identificacao"
    grupo["identificacao"] = unidade
    grupo["elegiveis"] = []
    grupo["quantidade"] = 1
    grupo["revisados"] = 1 if unidade["revisada"] else 0
    grupo["pendentes"] = 0 if unidade["revisada"] else 1
    grupo["percentual"] = 100 if unidade["revisada"] else 0
    if unidade["revisada"]:
        grupo["situacao"], grupo["classe"], grupo["icone"] = "Conferido", "grupo-conferido", "✓"
    else:
        grupo["situacao"], grupo["classe"], grupo["icone"] = "Aguardando conferência", "grupo-aguardando", "○"
    return grupo


def _gravar(termo, usuario, linha, valor: str, status: str, observacao: str = "") -> CampoInstrumento:
    campo = linha["campo"]
    if campo is None:
        campo = CampoInstrumento(termo=termo, nome=linha["nome"], metodo=linha["metodo"] or "deterministico")
    elif campo.validado_por_id and status == StatusCampo.VALIDADO:
        return campo
    if not (campo.valor_extraido or "").strip():
        campo.valor_extraido = linha["extraido"]
    campo.rotulo = linha["rotulo"]
    campo.valor_validado = valor
    campo.status = status
    campo.observacao = observacao
    campo.validado_por = usuario
    campo.validado_em = timezone.now()
    campo.pagina = linha["pagina"]
    campo.trecho = linha["trecho"]
    campo.save()
    return campo


def confirmar_identificacao(termo, usuario) -> list[CampoInstrumento]:
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    por_nome = {campo.nome: campo for campo in termo.campos.all()}
    gravados = []
    for linha in listar_atributos(termo, por_nome):
        if not linha["elegivel"]:
            continue
        gravados.append(_gravar(termo, usuario, linha, linha["extraido"], StatusCampo.VALIDADO))
    if not gravados:
        raise ValueError("Nenhum atributo elegível. Ausência não é confirmada.")
    return gravados


def corrigir_atributo_identificacao(termo, usuario, chave: str, valor: str, observacao: str) -> CampoInstrumento:
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    if chave not in {item[0] for item in CATALOGO}:
        raise ValueError("Atributo da identificação não reconhecido.")
    por_nome = {campo.nome: campo for campo in termo.campos.all()}
    linha = next(item for item in listar_atributos(termo, por_nome) if item["chave"] == chave)
    valor = _texto(valor)
    if not valor and not linha["extraido"]:
        raise ValueError("Atributo não identificado não é confirmado por correção vazia.")
    if valor != linha["extraido"] and not _texto(observacao):
        raise ValueError("A correção do atributo exige justificativa. O valor extraído permanece.")
    status = StatusCampo.CORRIGIDO if valor != linha["extraido"] else StatusCampo.VALIDADO
    return _gravar(termo, usuario, linha, valor, status, _texto(observacao))


CHAVES_LLM = ("tipo_instrumento", "numero_instrumento", "numero_processo", "municipio_convenente")


def interpretar_atributo(valor, fonte: str) -> dict:
    """Aceita só trecho literal. Não chama provedor."""
    from aplicacao.instrumentos.estruturacao_partes import recorte_literal

    if valor is None or not str(valor).strip():
        return {
            "valor_extraido": None,
            "valor_normalizado": None,
            "situacao": "nao_localizado",
        }
    literal = recorte_literal(valor, fonte)
    if not literal:
        return {
            "valor_extraido": None,
            "valor_normalizado": None,
            "situacao": "rejeitado",
        }
    return {
        "valor_extraido": literal,
        "valor_normalizado": literal,
        "situacao": "pendente",
    }
