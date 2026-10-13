"""Base normativa da preparação. Reusa referências já extraídas e o catálogo de normas.

Não inventa vigência, não confirma o instrumento e não chama modelo de linguagem.
"""

import re

from django.db import transaction
from django.utils import timezone

from aplicacao.documentos.validacao import validar_envio
from aplicacao.instrumentos.escolhas import StatusCorrespondenciaNorma
from aplicacao.instrumentos.extracao import _normas
from aplicacao.instrumentos.models import ReferenciaNormativaExtraida, TermoFomento
from aplicacao.normas.armazenamento import armazenar_pdf
from aplicacao.normas.escolhas import Esfera, SituacaoNorma, TipoNorma
from aplicacao.normas.models import Norma

_POLITICA = re.compile(r"\b(Pol[ií]tica\s+de\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][^,.;\n]{2,60})")


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _chave(tipo: str, numero: str, ano: str) -> tuple[str, str, str]:
    return ((tipo or "").casefold(), _digitos(numero), str(ano or "").strip())


def _tipo_catalogo(tipo: str) -> str:
    base = (tipo or "").casefold()
    if "decreto" in base:
        return TipoNorma.DECRETO
    if "resolu" in base:
        return TipoNorma.RESOLUCAO
    if "lei" in base:
        return TipoNorma.LEI
    if "pol" in base:
        return TipoNorma.OUTRO
    return ""


def complementar_referencias(termo: TermoFomento) -> int:
    from aplicacao.instrumentos.estruturacao_partes import texto_do_termo

    texto = texto_do_termo(termo)
    existentes = set(termo.referencias_normativas.values_list("texto", flat=True))
    novos = []
    for item in _normas(texto):
        if item["texto"] not in existentes:
            novos.append(item)
            existentes.add(item["texto"])
    for achado in _POLITICA.finditer(texto or ""):
        frase = " ".join(achado.group(1).split())
        if frase not in existentes:
            novos.append({"tipo": "Política", "numero": "", "ano": "", "esfera": "", "texto": frase})
            existentes.add(frase)
    for item in novos:
        ReferenciaNormativaExtraida.objects.create(
            termo=termo,
            tipo=(item.get("tipo") or "")[:40],
            numero=(item.get("numero") or "")[:40],
            ano=(item.get("ano") or "")[:8],
            esfera=(item.get("esfera") or "")[:40],
            texto=(item.get("texto") or "")[:255],
            trecho=(item.get("texto") or "")[:2000],
        )
    return len(novos)


def _candidatas(tipo: str, numero: str, ano: str):
    tipo_catalogo = _tipo_catalogo(tipo)
    if not tipo_catalogo or not _digitos(numero) or not str(ano or "").isdigit():
        return Norma.objects.none()
    return Norma.objects.filter(
        desativada_em__isnull=True,
        tipo_norma=tipo_catalogo,
        ano=int(ano),
    )


def associar_catalogo(referencias: list[ReferenciaNormativaExtraida]) -> None:
    for referencia in referencias:
        if referencia.norma_id:
            continue
        iguais = [
            norma
            for norma in _candidatas(referencia.tipo, referencia.numero, referencia.ano)
            if _digitos(norma.numero) == _digitos(referencia.numero)
        ]
        if len(iguais) != 1:
            if not iguais and referencia.status_correspondencia == StatusCorrespondenciaNorma.NAO_CONFRONTADA:
                referencia.status_correspondencia = StatusCorrespondenciaNorma.SEM_CORRESPONDENCIA
                referencia.save(update_fields=["status_correspondencia"])
            continue
        referencia.norma = iguais[0]
        referencia.status_correspondencia = StatusCorrespondenciaNorma.CORRESPONDENTE
        referencia.save(update_fields=["norma", "status_correspondencia"])


def _vigencia(norma) -> str:
    if norma is None or norma.inicio_vigencia is None:
        return "Não verificada"
    fim = norma.fim_vigencia.strftime("%d/%m/%Y") if norma.fim_vigencia else "sem fim informado"
    return f"{norma.inicio_vigencia.strftime('%d/%m/%Y')} — {fim}"


def _situacao(referencias, norma) -> str:
    if any(item.validado_por_id for item in referencias):
        return "Validado"
    if norma is None or not (norma.arquivo or "").strip():
        return "Documento necessário"
    if norma.inicio_vigencia is None or norma.situacao == SituacaoNorma.NAO_VERIFICADA:
        return "Requer verificação"
    return "Aguardando validação"


def montar_linhas(termo: TermoFomento) -> list[dict]:
    complementar_referencias(termo)
    referencias = list(termo.referencias_normativas.select_related("norma").order_by("id"))
    associar_catalogo(referencias)
    referencias = list(termo.referencias_normativas.select_related("norma").order_by("id"))
    grupos: dict[tuple, list] = {}
    for referencia in referencias:
        grupos.setdefault(_chave(referencia.tipo, referencia.numero, referencia.ano), []).append(referencia)
    linhas = []
    for chave, itens in grupos.items():
        norma = next((item.norma for item in itens if item.norma_id), None)
        principal = itens[0]
        linhas.append(
            {
                "chave": "-".join(chave),
                "referencia": principal,
                "referencias": itens,
                "norma": norma,
                "nome": principal.tipo or "Norma",
                "texto": principal.texto,
                "documento": "Disponível" if norma is not None and (norma.arquivo or "").strip() else "Ausente",
                "vigencia": _vigencia(norma),
                "situacao": _situacao(itens, norma),
                "pagina": principal.pagina,
                "trecho": principal.trecho if principal.trecho and principal.trecho != principal.texto else "",
            }
        )
    return linhas


def receber_documento(termo: TermoFomento, referencia: ReferenciaNormativaExtraida, arquivo, usuario) -> Norma:
    if referencia.termo_id != termo.pk:
        raise ValueError("A referência não pertence a este instrumento.")
    conteudo = arquivo.read()
    info = validar_envio(arquivo.name, conteudo, arquivo.content_type or "")
    tipo = _tipo_catalogo(referencia.tipo) or TipoNorma.OUTRO
    if not str(referencia.ano or "").isdigit():
        raise ValueError("A referência não tem ano identificável. Nenhum documento foi gravado.")
    with transaction.atomic():
        norma = Norma.objects.create(
            tipo_norma=tipo,
            numero=(referencia.numero or "")[:40],
            ano=int(referencia.ano),
            titulo=(referencia.texto or "Norma citada no instrumento")[:300],
            esfera=Esfera.UNIAO if (referencia.esfera or "").casefold() == "federal" else "",
            situacao=SituacaoNorma.NAO_VERIFICADA,
            fonte="Instrumento da parceria",
            hash_sha256=info["hash_sha256"],
            nome_original=arquivo.name,
            criado_por=usuario,
        )
        norma.arquivo = armazenar_pdf(norma.pk, conteudo)
        norma.save(update_fields=["arquivo", "atualizado_em"])
        chave = _chave(referencia.tipo, referencia.numero, referencia.ano)
        for item in termo.referencias_normativas.all():
            if _chave(item.tipo, item.numero, item.ano) != chave:
                continue
            item.norma = norma
            item.status_correspondencia = StatusCorrespondenciaNorma.CORRESPONDENTE
            item.save(update_fields=["norma", "status_correspondencia"])
    return norma


def validar_referencia(termo: TermoFomento, referencia: ReferenciaNormativaExtraida, usuario) -> None:
    if referencia.termo_id != termo.pk:
        raise ValueError("A referência não pertence a este instrumento.")
    if referencia.norma_id is None or not (referencia.norma.arquivo or "").strip():
        raise ValueError("Envie o documento da norma antes de validar a referência.")
    agora = timezone.now()
    chave = _chave(referencia.tipo, referencia.numero, referencia.ano)
    for item in termo.referencias_normativas.all():
        if _chave(item.tipo, item.numero, item.ano) != chave:
            continue
        item.validado_por = usuario
        item.validado_em = agora
        item.save(update_fields=["validado_por", "validado_em"])
