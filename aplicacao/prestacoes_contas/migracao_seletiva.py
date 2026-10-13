"""Exportação e importação de um processo, sem copiar o banco inteiro.

Não inclui senha, chave de API nem arquivo de ambiente. Não reexecuta OCR nem modelo.
A importação recusa processo, documento ou usuário já conflitante.
"""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime

from aplicacao.documentos.armazenamento import armazenar_pdf, ler_arquivo, remover_arquivo
from aplicacao.documentos.models import DadoExtraidoDocumento, Documento, PaginaDocumento, ReprocessamentoDocumento
from aplicacao.instrumentos.models import (
    AplicacaoFinanceiraEsperada,
    CampoInstrumento,
    ClausulaInstrumento,
    ConsequenciaInstrumento,
    ContaBancariaEsperada,
    ObrigacaoInstrumento,
    ParteInstrumento,
    PreparacaoInstrumento,
    ReferenciaNormativaExtraida,
    RegraDerivadaInstrumento,
    RegraTemporal,
    TermoFomento,
    VersaoTermoCongelada,
)
from aplicacao.prestacoes_contas.models import PrestacaoContas

VERSAO_FORMATO = 1
POLITICA_EXIGIR = "exigir"
POLITICA_DESVINCULAR = "desvincular"
_SEGREDO = re.compile(r"(sk-[A-Za-z0-9_\-]{6,}|Bearer\s+\S+)", re.IGNORECASE)

MODELOS = (
    PrestacaoContas,
    Documento,
    PaginaDocumento,
    DadoExtraidoDocumento,
    ReprocessamentoDocumento,
    TermoFomento,
    ClausulaInstrumento,
    ParteInstrumento,
    ObrigacaoInstrumento,
    RegraTemporal,
    AplicacaoFinanceiraEsperada,
    ContaBancariaEsperada,
    ReferenciaNormativaExtraida,
    ConsequenciaInstrumento,
    RegraDerivadaInstrumento,
    CampoInstrumento,
    VersaoTermoCongelada,
    PreparacaoInstrumento,
)
COBERTOS = {modelo._meta.label_lower for modelo in MODELOS}
COBERTOS.update(
    {
        "auditoria.registroauditoria",
        "inteligencia_artificial.usointeligenciaartificial",
    }
)
PROMPT = "inteligencia_artificial.versaopromptinteligenciaartificial"
MODELO_IA = "inteligencia_artificial.modelointeligenciaartificial"


class ConflitoMigracao(Exception):
    def __init__(self, mensagem, conflitos=None):
        self.conflitos = list(conflitos or [])
        super().__init__(mensagem)


def exportar_processo(numero_processo: str, destino: Path) -> dict:
    prestacao = PrestacaoContas.objects.get(numero_processo=numero_processo)
    documentos = list(Documento.objects.filter(prestacao_contas=prestacao).order_by("pk"))
    termos = list(TermoFomento.objects.filter(documento__in=documentos).order_by("pk"))
    _exigir_cobertura(prestacao, documentos, termos)
    registros = []
    for modelo, queryset in _consultas(prestacao, documentos, termos):
        for objeto in queryset.order_by("pk"):
            registros.append(_serializar(objeto))
    destino = Path(destino)
    pasta_arquivos = destino / "arquivos"
    pasta_arquivos.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for documento in documentos:
        if not documento.hash_sha256:
            raise ConflitoMigracao(f"Documento {documento.pk} está sem hash.")
        conteudo = ler_arquivo(documento.nome_armazenado).read_bytes()
        resumo = hashlib.sha256(conteudo).hexdigest()
        if resumo != documento.hash_sha256:
            raise ConflitoMigracao(f"O arquivo do documento {documento.pk} não confere com o hash gravado.")
        (pasta_arquivos / f"{resumo}.pdf").write_bytes(conteudo)
        arquivos.append({"hash_sha256": resumo, "arquivo": f"arquivos/{resumo}.pdf", "tamanho": len(conteudo)})
    pacote = {
        "versao_formato": VERSAO_FORMATO,
        "numero_processo": prestacao.numero_processo,
        "usuarios": _usuarios(registros),
        "arquivos": arquivos,
        "registros": registros,
    }
    (destino / "manifesto.json").write_text(json.dumps(pacote, ensure_ascii=False, cls=DjangoJSONEncoder), encoding="utf-8")
    return _contagens(registros, arquivos)


def conferir_pacote(origem: Path, politica_catalogo: str = POLITICA_EXIGIR) -> dict:
    pacote = _ler_pacote(origem)
    conflitos = _conflitos(pacote, politica_catalogo, Path(origem))
    return {"numero_processo": pacote["numero_processo"], "conflitos": conflitos, "contagens": _contagens(pacote["registros"], pacote["arquivos"])}


def importar_processo(origem: Path, aplicar: bool = False, politica_catalogo: str = POLITICA_EXIGIR) -> dict:
    pacote = _ler_pacote(origem)
    conflitos = _conflitos(pacote, politica_catalogo, Path(origem))
    if conflitos:
        raise ConflitoMigracao("A importação foi interrompida por conflito de identidade.", conflitos)
    if not aplicar:
        return {"aplicado": False, "numero_processo": pacote["numero_processo"], "contagens": _contagens(pacote["registros"], pacote["arquivos"])}
    with transaction.atomic():
        gravados = []
        try:
            resultado = _gravar(pacote, Path(origem), politica_catalogo, gravados)
        except Exception:
            for relativo in gravados:
                remover_arquivo(relativo)
            raise
    return resultado


def _consultas(prestacao, documentos, termos):
    ids_documentos = [documento.pk for documento in documentos]
    ids_termos = [termo.pk for termo in termos]
    auditoria = apps.get_model("auditoria", "RegistroAuditoria")
    uso = apps.get_model("inteligencia_artificial", "UsoInteligenciaArtificial")
    filtro_auditoria = Q(detalhes__prestacao=prestacao.pk) | Q(detalhes__prestacao=str(prestacao.pk))
    filtro_auditoria |= Q(detalhes__documento__in=ids_documentos) | Q(detalhes__documento__in=[str(valor) for valor in ids_documentos])
    return (
        (PrestacaoContas, PrestacaoContas.objects.filter(pk=prestacao.pk)),
        (Documento, Documento.objects.filter(pk__in=ids_documentos)),
        (PaginaDocumento, PaginaDocumento.objects.filter(documento_id__in=ids_documentos)),
        (DadoExtraidoDocumento, DadoExtraidoDocumento.objects.filter(documento_id__in=ids_documentos)),
        (ReprocessamentoDocumento, ReprocessamentoDocumento.objects.filter(documento_id__in=ids_documentos)),
        (TermoFomento, TermoFomento.objects.filter(pk__in=ids_termos)),
        (ClausulaInstrumento, ClausulaInstrumento.objects.filter(termo_id__in=ids_termos)),
        (ParteInstrumento, ParteInstrumento.objects.filter(termo_id__in=ids_termos)),
        (ObrigacaoInstrumento, ObrigacaoInstrumento.objects.filter(termo_id__in=ids_termos)),
        (RegraTemporal, RegraTemporal.objects.filter(termo_id__in=ids_termos)),
        (AplicacaoFinanceiraEsperada, AplicacaoFinanceiraEsperada.objects.filter(termo_id__in=ids_termos)),
        (ContaBancariaEsperada, ContaBancariaEsperada.objects.filter(termo_id__in=ids_termos)),
        (ReferenciaNormativaExtraida, ReferenciaNormativaExtraida.objects.filter(termo_id__in=ids_termos)),
        (ConsequenciaInstrumento, ConsequenciaInstrumento.objects.filter(termo_id__in=ids_termos)),
        (RegraDerivadaInstrumento, RegraDerivadaInstrumento.objects.filter(termo_id__in=ids_termos)),
        (CampoInstrumento, CampoInstrumento.objects.filter(termo_id__in=ids_termos)),
        (VersaoTermoCongelada, VersaoTermoCongelada.objects.filter(termo_id__in=ids_termos)),
        (PreparacaoInstrumento, PreparacaoInstrumento.objects.filter(prestacao=prestacao)),
        (auditoria, auditoria.objects.filter(filtro_auditoria)),
        (uso, uso.objects.filter(prestacao_contas=prestacao)),
    )


def _exigir_cobertura(prestacao, documentos, termos):
    pendencias = []
    for objeto in (prestacao, *documentos, *termos):
        for relacao in objeto._meta.related_objects:
            rotulo = relacao.related_model._meta.label_lower
            if rotulo in COBERTOS:
                continue
            try:
                ligado = getattr(objeto, relacao.get_accessor_name())
            except Exception:
                continue
            if hasattr(ligado, "exists"):
                if ligado.exists():
                    pendencias.append(rotulo)
            else:
                pendencias.append(rotulo)
    if pendencias:
        raise ConflitoMigracao("Há dependências do processo fora da migração seletiva.", sorted(set(pendencias)))


def _serializar(objeto) -> dict:
    campos = {}
    relacoes = {}
    for campo in objeto._meta.concrete_fields:
        if campo.primary_key:
            continue
        tipo = _tipo_relacao(campo)
        if tipo == "valor":
            campos[campo.name] = _limpar(getattr(objeto, campo.name))
            continue
        identificador = getattr(objeto, campo.attname)
        if tipo == "usuario":
            relacoes[campo.attname] = None if identificador is None else campo.related_model.objects.get(pk=identificador).username
        elif tipo == "prompt":
            relacoes[campo.attname] = None if identificador is None else _prompt(campo.related_model.objects.get(pk=identificador))
        elif tipo == "modelo":
            relacoes[campo.attname] = None if identificador is None else _modelo(campo.related_model.objects.get(pk=identificador))
        elif tipo == "remap":
            relacoes[campo.attname] = identificador
        elif identificador is not None:
            raise ConflitoMigracao(f"{objeto._meta.label_lower}.{campo.attname} aponta para um cadastro que esta migração não copia.")
    return {"model": objeto._meta.label_lower, "pk": objeto.pk, "campos": campos, "relacoes": relacoes}


def _tipo_relacao(campo) -> str:
    if not getattr(campo, "is_relation", False) or campo.related_model is None:
        return "valor"
    rotulo = campo.related_model._meta.label_lower
    if campo.related_model == get_user_model():
        return "usuario"
    if rotulo == PROMPT:
        return "prompt"
    if rotulo == MODELO_IA:
        return "modelo"
    if rotulo in COBERTOS:
        return "remap"
    return "bloquear"


def _prompt(versao) -> dict:
    return {"prompt": versao.prompt.codigo, "versao": versao.versao}


def _modelo(modelo) -> dict:
    return {"provedor": modelo.provedor, "identificador": modelo.identificador_modelo}


def _limpar(valor):
    if isinstance(valor, str):
        return _SEGREDO.sub("[removido]", valor)
    if isinstance(valor, dict):
        return {chave: _limpar(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [_limpar(item) for item in valor]
    return valor


def _usuarios(registros) -> list[dict]:
    nomes = set()
    for registro in registros:
        for nome in registro["relacoes"].values():
            if isinstance(nome, str):
                nomes.add(nome)
    Usuario = get_user_model()
    return [
        {"username": usuario.username, "perfil": usuario.perfil}
        for usuario in Usuario.objects.filter(username__in=nomes).order_by("username")
    ]


def _ler_pacote(origem: Path) -> dict:
    manifesto = Path(origem) / "manifesto.json"
    pacote = json.loads(manifesto.read_text(encoding="utf-8"))
    if pacote.get("versao_formato") != VERSAO_FORMATO:
        raise ConflitoMigracao("A versão do pacote não é compatível com esta importação.")
    return pacote


def _conflitos(pacote, politica_catalogo, origem: Path) -> list[str]:
    conflitos = []
    if PrestacaoContas.objects.filter(numero_processo=pacote["numero_processo"]).exists():
        conflitos.append(f"O processo {pacote['numero_processo']} já existe no destino.")
    Usuario = get_user_model()
    for usuario in pacote["usuarios"]:
        if not Usuario.objects.filter(username=usuario["username"]).exists():
            conflitos.append(f"Usuário {usuario['username']} não existe no destino.")
    for arquivo in pacote["arquivos"]:
        if Documento.objects.filter(hash_sha256=arquivo["hash_sha256"]).exists():
            conflitos.append(f"Já existe documento com o hash {arquivo['hash_sha256']}.")
        caminho = origem / arquivo["arquivo"]
        if not caminho.is_file() or hashlib.sha256(caminho.read_bytes()).hexdigest() != arquivo["hash_sha256"]:
            conflitos.append(f"Arquivo {arquivo['hash_sha256']} ausente ou inconsistente no pacote.")
    uso = apps.get_model("inteligencia_artificial", "UsoInteligenciaArtificial")
    prompt = apps.get_model("inteligencia_artificial", "VersaoPromptInteligenciaArtificial")
    modelo = apps.get_model("inteligencia_artificial", "ModeloInteligenciaArtificial")
    for registro in pacote["registros"]:
        if registro["model"] == "inteligencia_artificial.usointeligenciaartificial":
            chave = registro["campos"].get("chave_idempotencia")
            if chave and uso.objects.filter(chave_idempotencia=chave).exists():
                conflitos.append(f"A chave de uso {chave} já existe no destino.")
        for nome, referencia in registro["relacoes"].items():
            if not isinstance(referencia, dict):
                continue
            if "prompt" in referencia and not prompt.objects.filter(prompt__codigo=referencia["prompt"], versao=referencia["versao"]).exists():
                if politica_catalogo == POLITICA_EXIGIR:
                    conflitos.append(f"Prompt {referencia['prompt']} versão {referencia['versao']} não existe no destino.")
            if "identificador" in referencia and not modelo.objects.filter(provedor=referencia["provedor"], identificador_modelo=referencia["identificador"]).exists():
                if politica_catalogo == POLITICA_EXIGIR:
                    conflitos.append(f"Modelo {referencia['provedor']}/{referencia['identificador']} não existe no destino.")
    return sorted(set(conflitos))


def _gravar(pacote, origem, politica_catalogo, gravados) -> dict:
    mapas = {}
    congelamentos = []
    prestacao_id = None
    for registro in pacote["registros"]:
        modelo = apps.get_model(registro["model"])
        atributos, relacoes = _atributos(modelo, registro, mapas, politica_catalogo)
        if modelo is Documento:
            arquivo = next(item for item in pacote["arquivos"] if item["hash_sha256"] == atributos["hash_sha256"])
            conteudo = (origem / arquivo["arquivo"]).read_bytes()
            if hashlib.sha256(conteudo).hexdigest() != arquivo["hash_sha256"]:
                raise ConflitoMigracao("O arquivo do pacote não confere com o hash declarado.")
            atributos["nome_armazenado"] = armazenar_pdf(prestacao_id, conteudo)
            gravados.append(atributos["nome_armazenado"])
        if modelo is TermoFomento:
            congelamentos.append((registro["pk"], atributos.get("congelado"), atributos.get("hash_congelado"), atributos.get("status_validacao"), atributos.get("congelado_em"), atributos.get("validado_em")))
            atributos["congelado"] = False
        objeto = modelo(**atributos)
        for nome, valor in relacoes.items():
            setattr(objeto, nome, valor)
        objeto.save()
        mapas[(registro["model"], registro["pk"])] = objeto.pk
        if modelo is PrestacaoContas:
            prestacao_id = objeto.pk
        tempos = {}
        for nome in ("criado_em", "atualizado_em", "data_hora", "iniciada_em"):
            if nome in registro["campos"] and registro["campos"][nome] is not None:
                campo = modelo._meta.get_field(nome)
                tempos[nome] = _valor_campo(campo, registro["campos"][nome])
        if tempos:
            modelo.objects.filter(pk=objeto.pk).update(**tempos)
    for antigo, congelado, resumo, status, congelado_em, validado_em in congelamentos:
        TermoFomento.objects.filter(pk=mapas[("instrumentos.termofomento", antigo)]).update(
            congelado=bool(congelado),
            hash_congelado=resumo or "",
            status_validacao=status,
            congelado_em=congelado_em,
            validado_em=validado_em,
        )
    return {
        "aplicado": True,
        "numero_processo": pacote["numero_processo"],
        "prestacao_id": prestacao_id,
        "contagens": _contagens(pacote["registros"], pacote["arquivos"]),
        "arquivos": list(gravados),
    }


def _atributos(modelo, registro, mapas, politica_catalogo):
    atributos = {}
    relacoes = {}
    for campo in modelo._meta.concrete_fields:
        if campo.primary_key or campo.name not in registro["campos"]:
            continue
        valor = _valor_campo(campo, registro["campos"][campo.name])
        if campo.get_internal_type() == "JSONField":
            valor = _reescrever_identidades(valor, mapas)
        atributos[campo.name] = valor
    for nome, referencia in registro["relacoes"].items():
        campo = modelo._meta.get_field(nome)
        relacoes[nome] = _resolver(campo, referencia, mapas, politica_catalogo)
    return atributos, relacoes


def _resolver(campo, referencia, mapas, politica_catalogo):
    if referencia is None:
        return None
    tipo = _tipo_relacao(campo)
    if tipo == "usuario":
        return get_user_model().objects.get(username=referencia).pk
    if tipo == "remap":
        return mapas[(campo.related_model._meta.label_lower, referencia)]
    if tipo == "prompt":
        versao = apps.get_model("inteligencia_artificial", "VersaoPromptInteligenciaArtificial").objects.filter(
            prompt__codigo=referencia["prompt"], versao=referencia["versao"]
        ).first()
        if versao is None and politica_catalogo == POLITICA_DESVINCULAR:
            return None
        return versao.pk
    if tipo == "modelo":
        modelo = apps.get_model("inteligencia_artificial", "ModeloInteligenciaArtificial").objects.filter(
            provedor=referencia["provedor"], identificador_modelo=referencia["identificador"]
        ).first()
        if modelo is None and politica_catalogo == POLITICA_DESVINCULAR:
            return None
        return modelo.pk
    raise ConflitoMigracao(f"Relação {campo.attname} não pode ser resolvida.")


def _reescrever_identidades(valor, mapas):
    if isinstance(valor, list):
        return [_reescrever_identidades(item, mapas) for item in valor]
    if not isinstance(valor, dict):
        return valor
    novo = {}
    for chave, item in valor.items():
        if chave in {"prestacao", "prestacao_contas"}:
            novo[chave] = _mapa("prestacoes_contas.prestacaocontas", item, mapas)
        elif chave == "documento":
            novo[chave] = _mapa("documentos.documento", item, mapas)
        else:
            novo[chave] = _reescrever_identidades(item, mapas)
    return novo


def _mapa(rotulo, item, mapas):
    if (rotulo, item) in mapas:
        return mapas[(rotulo, item)]
    if isinstance(item, str) and item.isdigit() and (rotulo, int(item)) in mapas:
        return mapas[(rotulo, int(item))]
    return item


def _valor_campo(campo, valor):
    from django.db import models

    if valor is None:
        return None
    if isinstance(campo, models.DecimalField):
        return Decimal(valor)
    if isinstance(campo, models.DateTimeField) and isinstance(valor, str):
        return parse_datetime(valor)
    if isinstance(campo, models.DateField) and isinstance(valor, str):
        return parse_date(valor)
    return valor


def _contagens(registros, arquivos) -> dict:
    contagens = {"arquivos": len(arquivos)}
    for registro in registros:
        contagens[registro["model"]] = contagens.get(registro["model"], 0) + 1
    return contagens
