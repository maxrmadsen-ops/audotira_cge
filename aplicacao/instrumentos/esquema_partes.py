"""Contrato e conferência das partes. Não chama modelo de linguagem nem inventa atributo."""

from django.utils import timezone

from aplicacao.instrumentos.escolhas import StatusCampo
from aplicacao.instrumentos.models import CampoInstrumento, TermoCongelado

CAMPOS_AGREGADOS = frozenset({"concedente", "beneficiario"})
PREFIXO_ATRIBUTO = "parte_"
PAPEIS = ("concedente", "beneficiario", "interveniente")
ROTULO_UNIDADE = {
    "concedente": "Concedente",
    "beneficiario": "Convenente",
    "interveniente": "Interveniente",
}
SITUACOES = (
    "nao_localizado",
    "ilegivel",
    "ambiguo",
    "nao_aplicavel",
    "pendente",
    "validado",
    "corrigido",
)
CHAVES_CONTRATO = (
    "razao_social",
    "sigla",
    "cnpj",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "municipio",
    "estado",
    "cep",
    "representante_nome",
    "representante_cargo",
    "representante_cpf",
)
# Tabela compacta do que a versão atual consegue ler. O contrato JSON é mais fino.
CATALOGO_TELA = (
    ("razao_social", "Razão social", "nome"),
    ("sigla", "Sigla", "sigla"),
    ("cnpj", "CNPJ", "cnpj"),
    ("endereco", "Endereço", "endereco"),
    ("bairro", "Bairro", None),
    ("municipio_uf", "Município/UF", "municipio_uf"),
    ("representante", "Representante", "representante_nome"),
    ("cargo", "Cargo", "representante_cargo"),
    ("cpf", "CPF", "representante_cpf"),
)
STATUS_HUMANO = {
    StatusCampo.VALIDADO,
    StatusCampo.CORRIGIDO,
    StatusCampo.NAO_IDENTIFICADO,
    StatusCampo.REJEITADO,
}


def nome_atributo(papel: str, chave: str) -> str:
    return f"{PREFIXO_ATRIBUTO}{papel}_{chave}"


def atributo_ausente(pagina=None) -> dict:
    return {
        "valor": None,
        "normalizado": None,
        "pagina": pagina,
        "trecho": "",
        "situacao": "nao_localizado",
        "metodo": "",
        "versao": None,
    }


def atributo_extraido(valor: str, pagina=None, trecho: str = "", versao=None) -> dict:
    texto = (valor or "").strip()
    if not texto:
        return atributo_ausente(pagina)
    return {
        "valor": texto,
        "normalizado": texto,
        "pagina": pagina,
        "trecho": trecho or "",
        "situacao": "pendente",
        "metodo": "deterministico",
        "versao": versao,
    }


def esquema_parte() -> dict:
    atributo = {
        "type": "object",
        "additionalProperties": False,
        "required": ["valor", "normalizado", "pagina", "trecho", "situacao", "metodo", "versao"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["papel", *CHAVES_CONTRATO],
        "properties": {
            "papel": {"enum": list(PAPEIS)},
            **{chave: atributo for chave in CHAVES_CONTRATO},
        },
    }


def _valor_parte(parte, origem: str | None) -> str:
    if origem is None or parte is None:
        return ""
    if origem == "municipio_uf":
        municipio = (parte.municipio or "").strip()
        uf = (parte.uf or "").strip()
        if municipio and uf:
            return f"{municipio}/{uf}"
        return municipio or uf
    return (getattr(parte, origem, "") or "").strip()


def parte_para_contrato(parte, pagina=None, trecho: str = "", versao=None) -> dict:
    """Só copia o que já está no registro. Endereço não é dividido nem completado."""
    bruto = {
        "razao_social": _valor_parte(parte, "nome"),
        "sigla": _valor_parte(parte, "sigla"),
        "cnpj": _valor_parte(parte, "cnpj"),
        "municipio": (parte.municipio or "").strip() if parte else "",
        "estado": (parte.uf or "").strip() if parte else "",
        "representante_nome": _valor_parte(parte, "representante_nome"),
        "representante_cargo": _valor_parte(parte, "representante_cargo"),
        "representante_cpf": _valor_parte(parte, "representante_cpf"),
    }
    contrato = {"papel": parte.papel if parte else ""}
    for chave in CHAVES_CONTRATO:
        texto = bruto.get(chave, "")
        contrato[chave] = atributo_extraido(texto, pagina, trecho, versao) if texto else atributo_ausente(pagina)
    return contrato


def listar_atributos(parte, campos_por_nome: dict, agregado=None) -> list[dict]:
    pagina = agregado.pagina if agregado is not None else None
    trecho = (agregado.trecho or "") if agregado is not None else ""
    linhas = []
    for chave, rotulo, origem in CATALOGO_TELA:
        nome = nome_atributo(parte.papel, chave)
        campo = campos_por_nome.get(nome)
        extraido = _valor_parte(parte, origem) or ((campo.valor_extraido or "").strip() if campo is not None else "")
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
                "nome": nome,
                "rotulo": rotulo,
                "extraido": extraido,
                "exibicao": (campo.valor_validado if humano and campo.valor_validado else extraido),
                "situacao": situacao,
                "elegivel": bool(extraido) and not humano,
                "pagina": pagina,
                "trecho": trecho,
                "campo": campo,
                "unidade": ROTULO_UNIDADE.get(parte.papel, parte.papel),
            }
        )
    return linhas


def montar_unidades(termo, campos_por_nome: dict) -> list[dict]:
    unidades = []
    for parte in termo.partes.all():
        agregado = campos_por_nome.get(parte.papel if parte.papel in CAMPOS_AGREGADOS else "")
        linhas = listar_atributos(parte, campos_por_nome, agregado)
        elegiveis = [linha for linha in linhas if linha["elegivel"]]
        ausentes = [linha for linha in linhas if not linha["extraido"]]
        identificados = [linha for linha in linhas if linha["extraido"]]
        revisada = bool(linhas) and all(not linha["elegivel"] for linha in linhas if linha["extraido"]) and any(linha["extraido"] for linha in linhas)
        unidades.append(
            {
                "papel": parte.papel,
                "titulo": ROTULO_UNIDADE.get(parte.papel, parte.get_papel_display()),
                "papel_registrado": parte.get_papel_display(),
                "linhas": linhas,
                "elegiveis": elegiveis,
                "ausentes": ausentes,
                "identificados": identificados,
                "revisada": revisada,
                "pagina": agregado.pagina if agregado is not None else None,
                "trecho": (agregado.trecho or "") if agregado is not None else "",
                "validacao_anterior": bool(agregado and agregado.validado_por_id),
            }
        )
    return unidades


def aplicar_partes(grupo: dict, termo, campos_por_nome: dict) -> dict:
    unidades = montar_unidades(termo, campos_por_nome)
    if not unidades:
        grupo["tipo"] = ""
        return grupo
    revisadas = sum(1 for unidade in unidades if unidade["revisada"])
    grupo["tipo"] = "partes"
    grupo["unidades_parte"] = unidades
    grupo["elegiveis"] = []
    grupo["quantidade"] = len(unidades)
    grupo["revisados"] = revisadas
    grupo["pendentes"] = len(unidades) - revisadas
    grupo["percentual"] = round(100 * revisadas / len(unidades)) if unidades else 0
    if revisadas == len(unidades):
        grupo["situacao"], grupo["classe"], grupo["icone"] = "Conferido", "grupo-conferido", "✓"
    elif revisadas:
        grupo["situacao"], grupo["classe"], grupo["icone"] = "Em conferência", "grupo-parcial", "◔"
    else:
        grupo["situacao"], grupo["classe"], grupo["icone"] = "Aguardando conferência", "grupo-aguardando", "○"
    return grupo


def confirmar_parte(termo, usuario, papel: str) -> list[CampoInstrumento]:
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    if papel not in CAMPOS_AGREGADOS:
        raise ValueError("A unidade de parte não foi reconhecida.")
    parte = termo.partes.filter(papel=papel).first()
    if parte is None:
        raise ValueError("Esta parte não está registrada no instrumento.")
    por_nome = {campo.nome: campo for campo in termo.campos.all()}
    agregado = por_nome.get(papel)
    gravados = []
    for linha in listar_atributos(parte, por_nome, agregado):
        if not linha["elegivel"]:
            continue
        campo = linha["campo"]
        if campo is None:
            campo = CampoInstrumento(termo=termo, nome=linha["nome"], metodo="parte_existente")
        elif campo.validado_por_id:
            continue
        campo.rotulo = f"{linha['unidade']} · {linha['rotulo']}"
        campo.valor_extraido = linha["extraido"]
        campo.valor_validado = linha["extraido"]
        campo.status = StatusCampo.VALIDADO
        campo.validado_por = usuario
        campo.validado_em = timezone.now()
        campo.pagina = linha["pagina"]
        campo.trecho = linha["trecho"]
        campo.metodo = campo.metodo or "parte_existente"
        campo.save()
        gravados.append(campo)
    if not gravados:
        raise ValueError("Nenhum atributo elegível. Ausência não é confirmada.")
    return gravados


def corrigir_atributo_parte(termo, usuario, papel: str, chave: str, valor: str, observacao: str) -> CampoInstrumento:
    if termo.congelado:
        raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
    if papel not in CAMPOS_AGREGADOS or chave not in {item[0] for item in CATALOGO_TELA}:
        raise ValueError("Atributo da parte não reconhecido.")
    parte = termo.partes.filter(papel=papel).first()
    if parte is None:
        raise ValueError("Esta parte não está registrada no instrumento.")
    por_nome = {campo.nome: campo for campo in termo.campos.all()}
    agregado = por_nome.get(papel)
    linha = next(item for item in listar_atributos(parte, por_nome, agregado) if item["chave"] == chave)
    valor = (valor or "").strip()
    if not valor and not linha["extraido"]:
        raise ValueError("Atributo não identificado não é confirmado por correção vazia.")
    if valor != linha["extraido"] and not (observacao or "").strip():
        raise ValueError("A correção do atributo exige justificativa. O valor extraído permanece.")
    campo = linha["campo"]
    if campo is None:
        campo = CampoInstrumento(termo=termo, nome=linha["nome"], metodo="parte_existente")
    if not (campo.valor_extraido or "").strip():
        campo.valor_extraido = linha["extraido"]
    campo.rotulo = f"{linha['unidade']} · {linha['rotulo']}"
    campo.valor_validado = valor
    campo.status = StatusCampo.CORRIGIDO if valor != (campo.valor_extraido or "") else StatusCampo.VALIDADO
    campo.observacao = (observacao or "").strip()
    campo.validado_por = usuario
    campo.validado_em = timezone.now()
    campo.pagina = linha["pagina"]
    campo.trecho = linha["trecho"]
    campo.save()
    return campo
