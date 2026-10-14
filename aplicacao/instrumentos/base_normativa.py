"""Base normativa da preparação. Reusa referências já extraídas e o catálogo de normas.

A consolidação é só de leitura. Não altera texto, página, trecho, número nem ano
das citações. Não inventa vigência, não confirma o instrumento e não chama modelo.
"""

import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.validacao import validar_envio
from aplicacao.instrumentos.escolhas import StatusCorrespondenciaNorma
from aplicacao.instrumentos.extracao import _normas
from aplicacao.instrumentos.models import ReferenciaNormativaExtraida, TermoFomento
from aplicacao.normas.armazenamento import armazenar_pdf
from aplicacao.normas.escolhas import Esfera, EstadoVerificacaoVigencia, SituacaoNorma, TipoNorma
from aplicacao.normas.models import Norma, VerificacaoVigencia
from aplicacao.normas.servico import criar_nova_versao

_POLITICA = re.compile(r"\b(Pol[ií]tica\s+de\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][^,.;\n]{2,60})")


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _esfera(valor: str) -> str:
    return (valor or "").strip().casefold()


def _ano(valor: str) -> str:
    return (valor or "").strip()


def _ano_par(origem: str, destino: str) -> bool:
    if origem == destino:
        return True
    if len(origem) == 2 and len(destino) == 4 and origem.isdigit() and destino.isdigit() and destino.endswith(origem):
        return True
    if len(destino) == 2 and len(origem) == 4 and origem.isdigit() and destino.isdigit() and origem.endswith(destino):
        return True
    return False


def _chave(tipo: str, numero: str, ano: str) -> tuple[str, str, str]:
    return ((tipo or "").casefold(), _digitos(numero), _ano(ano))


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
    if not tipo_catalogo or not _digitos(numero) or not _ano(ano).isdigit():
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


def _unir_anos(refs: list) -> list[dict]:
    por_ano: dict[str, list] = {}
    for ref in refs:
        por_ano.setdefault(_ano(ref.ano), []).append(ref)
    grupos = [{"ano": ano, "refs": membros, "ambigua": False} for ano, membros in por_ano.items()]
    curtos = [grupo for grupo in grupos if len(grupo["ano"]) == 2 and grupo["ano"].isdigit()]
    longos = [grupo for grupo in grupos if len(grupo["ano"]) == 4 and grupo["ano"].isdigit()]
    outros = [grupo for grupo in grupos if grupo not in curtos and grupo not in longos]
    consumidos = set()
    for curto in curtos:
        alvos = [grupo for grupo in longos if grupo["ano"].endswith(curto["ano"])]
        if len(alvos) == 1:
            alvos[0]["refs"].extend(curto["refs"])
            consumidos.add(id(curto))
        elif len(alvos) > 1:
            curto["ambigua"] = True
    return longos + [grupo for grupo in curtos if id(grupo) not in consumidos] + outros


def _anos_do_grupo(grupo: dict) -> set[str]:
    return {_ano(ref.ano) for ref in grupo["refs"]}


def _grupo_ano_compativel(origem: dict, destino: dict) -> bool:
    anos_destino = _anos_do_grupo(destino)
    return all(any(_ano_par(_ano(ref.ano), outro) for outro in anos_destino) for ref in origem["refs"])


def consolidar_referencias(referencias: list) -> list[dict]:
    baldes: dict[tuple, list] = {}
    for ref in referencias:
        baldes.setdefault(((ref.tipo or "").casefold(), _digitos(ref.numero)), []).append(ref)
    saida = []
    for refs in baldes.values():
        por_esfera: dict[str, list] = {}
        vazias = []
        for ref in refs:
            esfera = _esfera(ref.esfera)
            if esfera:
                por_esfera.setdefault(esfera, []).append(ref)
            else:
                vazias.append(ref)
        ilhas = []
        for esfera, membros in por_esfera.items():
            for grupo in _unir_anos(membros):
                grupo["esfera"] = esfera
                ilhas.append(grupo)
        if not ilhas:
            for grupo in _unir_anos(refs):
                grupo["esfera"] = ""
                saida.append(grupo)
            continue
        for grupo in _unir_anos(vazias):
            alvos = [ilha for ilha in ilhas if _grupo_ano_compativel(grupo, ilha)]
            if len(alvos) == 1:
                alvos[0]["refs"].extend(grupo["refs"])
                alvos[0]["ambigua"] = alvos[0]["ambigua"] or grupo["ambigua"]
            else:
                grupo["esfera"] = ""
                grupo["ambigua"] = grupo["ambigua"] or len(alvos) > 1
                saida.append(grupo)
        saida.extend(ilhas)
    saida.sort(key=lambda grupo: min(item.pk for item in grupo["refs"]))
    for grupo in saida:
        grupo["refs"].sort(key=lambda item: item.pk)
    return saida


def _ano_exibicao(refs: list) -> str:
    longos = sorted({_ano(ref.ano) for ref in refs if len(_ano(ref.ano)) == 4 and _ano(ref.ano).isdigit()})
    if len(longos) == 1:
        return longos[0]
    curto = _ano(refs[0].ano)
    return curto if curto.isdigit() else ""


def _ano_canonico(refs: list) -> int:
    longos = sorted({_ano(ref.ano) for ref in refs if len(_ano(ref.ano)) == 4 and _ano(ref.ano).isdigit()})
    if len(longos) == 1:
        return int(longos[0])
    curto = _ano(refs[0].ano)
    if curto.isdigit():
        return int(curto)
    raise ValueError("A referência não tem ano identificável. Nenhum documento foi gravado.")


def _data_instrumento(termo: TermoFomento):
    return termo.data_assinatura or termo.vigencia_inicio or termo.data_celebracao


def _ids_cadeia(norma) -> list[int]:
    ids = []
    atual = norma
    while atual is not None and atual.pk not in ids:
        ids.append(atual.pk)
        atual = atual.norma_anterior
    return ids


def _verificacao_atual(termo, norma):
    if norma is None:
        return None
    return VerificacaoVigencia.objects.filter(termo=termo, norma=norma).order_by("-id").first()


def _verificacoes_da_cadeia(termo, norma) -> list:
    if norma is None:
        return []
    return list(
        VerificacaoVigencia.objects.filter(termo=termo, norma_id__in=_ids_cadeia(norma))
        .select_related("criado_por", "verificado_por", "norma")
        .order_by("-id")
    )


def _rotulo_vigencia(registro) -> str:
    if registro is None or registro.estado == EstadoVerificacaoVigencia.NAO_VERIFICADA:
        return "Não verificada"
    if registro.estado == EstadoVerificacaoVigencia.DATAS_INFORMADAS:
        return "Datas informadas"
    if registro.estado == EstadoVerificacaoVigencia.VERIFICADA:
        return "Vigência verificada"
    return "Divergência de vigência"


def _periodo(registro) -> str:
    if registro is None or registro.inicio_vigencia is None:
        return ""
    fim = registro.fim_vigencia.strftime("%d/%m/%Y") if registro.fim_vigencia else "sem fim informado"
    return f"{registro.inicio_vigencia.strftime('%d/%m/%Y')} — {fim}"


def _historico(referencias: list) -> list:
    ids = [ref.pk for ref in referencias]
    normas = [ref.norma_id for ref in referencias if ref.norma_id]
    if not ids and not normas:
        return []
    return list(
        RegistroAuditoria.objects.select_related("usuario")
        .filter(Q(detalhes__referencia__in=ids) | Q(detalhes__norma__in=normas))
        .order_by("-data_hora")[:30]
    )


def montar_linhas(termo: TermoFomento) -> list[dict]:
    referencias = list(termo.referencias_normativas.select_related("norma").order_by("id"))
    data = _data_instrumento(termo)
    linhas = []
    for grupo in consolidar_referencias(referencias):
        itens = grupo["refs"]
        principal = itens[0]
        normas = [item.norma for item in itens if item.norma_id and item.norma.desativada_em is None]
        distintas = {norma.pk for norma in normas}
        norma = normas[0] if normas else None
        documento_disponivel = bool(norma and (norma.arquivo or "").strip())
        validada = all(item.validado_por_id for item in itens) and documento_disponivel
        verificacao = _verificacao_atual(termo, norma)
        inconsistente = grupo["ambigua"] or len(distintas) > 1
        if inconsistente:
            indicador = "vermelho"
        elif validada:
            indicador = "azul"
        elif not documento_disponivel:
            indicador = "cinza"
        else:
            indicador = "amarelo"
        esferas = sorted({(item.esfera or "").strip() for item in itens if (item.esfera or "").strip()})
        orgao = (norma.orgao_emissor or "").strip() if norma and norma.orgao_emissor else ""
        if not documento_disponivel:
            situacao = "Documento pendente"
        elif validada:
            situacao = "Identificação conferida"
        else:
            situacao = "Documento disponível — aguardando conferência"
        linhas.append(
            {
                "chave": f"{(principal.tipo or '').casefold()}-{_digitos(principal.numero)}-{principal.pk}",
                "referencia": principal,
                "referencias": itens,
                "norma": norma,
                "tipo": principal.tipo or "Norma",
                "numero": next((item.numero for item in itens if len(_ano(item.ano)) == 4), principal.numero),
                "ano": _ano_exibicao(itens),
                "orgao": orgao,
                "esfera": ", ".join(esferas),
                "catalogo": "Correspondente" if norma else "Não confrontada com o catálogo",
                "documento": "Disponível" if documento_disponivel else "Ausente",
                "documento_disponivel": documento_disponivel,
                "vigencia": _rotulo_vigencia(verificacao),
                "estado_vigencia": verificacao.estado if verificacao else EstadoVerificacaoVigencia.NAO_VERIFICADA,
                "periodo": _periodo(verificacao),
                "fonte_vigencia": verificacao.fonte_documental if verificacao else "",
                "motivo_vigencia": verificacao.motivo_divergencia if verificacao else "",
                "verificacoes": _verificacoes_da_cadeia(termo, norma),
                "situacao": situacao,
                "validada": validada,
                "ambigua": grupo["ambigua"],
                "inconsistente": inconsistente,
                "indicador": indicador,
                "motivo": _motivo(grupo["ambigua"], len(distintas) > 1),
                "data_instrumento": data.strftime("%d/%m/%Y") if data else "Não identificada",
                "historico": _historico(itens),
            }
        )
    return linhas


def _motivo(ambigua: bool, normas_divergentes: bool) -> str:
    if ambigua:
        return "Referência ambígua. As citações não foram consolidadas."
    if normas_divergentes:
        return "As citações apontam para documentos normativos diferentes."
    return ""


def resumo_linhas(linhas: list[dict]) -> dict:
    return {
        "total": len(linhas),
        "com_documento": sum(1 for linha in linhas if linha["documento_disponivel"]),
        "sem_documento": sum(1 for linha in linhas if not linha["documento_disponivel"]),
        "validadas": sum(1 for linha in linhas if linha["validada"]),
        "inconsistencias": sum(1 for linha in linhas if linha["inconsistente"]),
    }


def mensagem_resumo(resumo: dict) -> str:
    total = resumo["total"]
    if total == 0:
        return "Nenhuma norma identificada no Termo de Fomento."
    normas = "1 norma identificada" if total == 1 else f"{total} normas identificadas"
    if resumo["com_documento"] == 0:
        documentos = "Nenhum documento normativo foi anexado."
    elif resumo["sem_documento"] == 0:
        documentos = "Todos os documentos normativos foram anexados."
    else:
        documentos = f"{resumo['com_documento']} com documento anexado e {resumo['sem_documento']} com documento pendente."
    if resumo["sem_documento"] or resumo["validadas"] < resumo["com_documento"]:
        conclusao = "Para concluir esta atividade, disponibilize e confira os documentos aplicáveis."
    elif resumo["inconsistencias"]:
        conclusao = "Há inconsistências documentais para revisar."
    else:
        conclusao = "As normas anexadas tiveram a identificação conferida."
    return f"{normas} no Termo de Fomento. {documentos} {conclusao}"


def grupo_da_referencia(termo: TermoFomento, referencia: ReferenciaNormativaExtraida) -> dict:
    for linha in montar_linhas(termo):
        if any(item.pk == referencia.pk for item in linha["referencias"]):
            return linha
    raise ValueError("A referência não pertence a este instrumento.")


def _situacao_grupo(linha: dict) -> str:
    if linha["validada"]:
        return "identificacao_validada"
    if linha["documento_disponivel"]:
        return "aguardando_conferencia"
    return "documento_ausente"


def receber_documento(termo: TermoFomento, referencia: ReferenciaNormativaExtraida, arquivo, usuario) -> Norma:
    if referencia.termo_id != termo.pk:
        raise ValueError("A referência não pertence a este instrumento.")
    linha = grupo_da_referencia(termo, referencia)
    if linha["ambigua"]:
        raise ValueError("A referência é ambígua e não foi consolidada. Nenhum documento foi gravado.")
    conteudo = arquivo.read()
    info = validar_envio(arquivo.name, conteudo, arquivo.content_type or "")
    tipo = _tipo_catalogo(linha["tipo"]) or TipoNorma.OUTRO
    ano = _ano_canonico(linha["referencias"])
    esfera = ""
    for item in linha["referencias"]:
        if _esfera(item.esfera) == "federal":
            esfera = Esfera.UNIAO
            break
        if _esfera(item.esfera) in {choice for choice, _rotulo in Esfera.choices}:
            esfera = _esfera(item.esfera)
            break
    with transaction.atomic():
        anterior = linha["norma"]
        if anterior is not None:
            norma = criar_nova_versao(
                anterior,
                usuario=usuario,
                conteudo=conteudo,
                nome_original=arquivo.name,
                dados={
                    "situacao": SituacaoNorma.NAO_VERIFICADA,
                    "inicio_vigencia": None,
                    "fim_vigencia": None,
                    "titulo": (referencia.texto or anterior.titulo)[:300],
                },
            )
        else:
            norma = Norma.objects.create(
                tipo_norma=tipo,
                numero=(linha["numero"] or "")[:40],
                ano=ano,
                titulo=(referencia.texto or "Norma citada no instrumento")[:300],
                esfera=esfera,
                situacao=SituacaoNorma.NAO_VERIFICADA,
                fonte="Instrumento da parceria",
                hash_sha256=info["hash_sha256"],
                nome_original=arquivo.name,
                criado_por=usuario,
            )
            norma.arquivo = armazenar_pdf(norma.pk, conteudo)
            norma.save(update_fields=["arquivo", "atualizado_em"])
        for item in linha["referencias"]:
            item.norma = norma
            item.status_correspondencia = StatusCorrespondenciaNorma.CORRESPONDENTE
            if anterior is not None:
                item.validado_por = None
                item.validado_em = None
                item.save(update_fields=["norma", "status_correspondencia", "validado_por", "validado_em"])
            else:
                item.save(update_fields=["norma", "status_correspondencia"])
    return norma


def validar_referencia(termo: TermoFomento, referencia: ReferenciaNormativaExtraida, usuario) -> None:
    if referencia.termo_id != termo.pk:
        raise ValueError("A referência não pertence a este instrumento.")
    linha = grupo_da_referencia(termo, referencia)
    if not linha["documento_disponivel"]:
        raise ValueError("Envie o documento da norma antes de validar a identificação.")
    agora = timezone.now()
    for item in linha["referencias"]:
        item.validado_por = usuario
        item.validado_em = agora
        item.save(update_fields=["validado_por", "validado_em"])


def _norma_do_grupo(termo: TermoFomento, referencia: ReferenciaNormativaExtraida) -> Norma:
    if referencia.termo_id != termo.pk:
        raise ValueError("A referência não pertence a este instrumento.")
    norma = grupo_da_referencia(termo, referencia)["norma"]
    if norma is None or not (norma.arquivo or "").strip():
        raise ValueError("Envie o documento da norma antes de tratar a vigência.")
    return norma


def informar_datas(
    termo: TermoFomento,
    referencia: ReferenciaNormativaExtraida,
    usuario,
    inicio: str,
    fim: str = "",
    fonte: str = "",
) -> VerificacaoVigencia:
    norma = _norma_do_grupo(termo, referencia)
    inicio_data = parse_date(inicio or "")
    if inicio_data is None:
        raise ValueError("Informe a data inicial do período.")
    fim_data = parse_date(fim) if (fim or "").strip() else None
    if (fim or "").strip() and fim_data is None:
        raise ValueError("A data final informada é inválida.")
    if fim_data and fim_data < inicio_data:
        raise ValueError("A data final não pode ser anterior à inicial.")
    if not (fonte or "").strip():
        raise ValueError("Informe a fonte documental do período.")
    return VerificacaoVigencia.objects.create(
        termo=termo,
        norma=norma,
        estado=EstadoVerificacaoVigencia.DATAS_INFORMADAS,
        inicio_vigencia=inicio_data,
        fim_vigencia=fim_data,
        fonte_documental=fonte.strip(),
        versao_documento=norma.versao,
        hash_sha256=norma.hash_sha256,
        criado_por=usuario,
    )


def verificar_vigencia(
    termo: TermoFomento,
    referencia: ReferenciaNormativaExtraida,
    usuario,
    fundamentacao: str,
    data_referencia: str,
) -> VerificacaoVigencia:
    norma = _norma_do_grupo(termo, referencia)
    atual = _verificacao_atual(termo, norma)
    if atual is None or atual.estado != EstadoVerificacaoVigencia.DATAS_INFORMADAS or atual.inicio_vigencia is None:
        raise ValueError("Informe o período antes de verificar a vigência.")
    if not (fundamentacao or "").strip() or not (data_referencia or "").strip():
        raise ValueError("A verificação exige fundamentação e data de referência.")
    referencia_data = parse_date(data_referencia)
    if referencia_data is None:
        raise ValueError("A data de referência é inválida.")
    return VerificacaoVigencia.objects.create(
        termo=termo,
        norma=norma,
        estado=EstadoVerificacaoVigencia.VERIFICADA,
        inicio_vigencia=atual.inicio_vigencia,
        fim_vigencia=atual.fim_vigencia,
        fonte_documental=atual.fonte_documental,
        data_referencia=referencia_data,
        fundamentacao=fundamentacao.strip(),
        versao_documento=norma.versao,
        hash_sha256=norma.hash_sha256,
        criado_por=usuario,
        verificado_por=usuario,
        verificado_em=timezone.now(),
    )


def registrar_divergencia_vigencia(
    termo: TermoFomento,
    referencia: ReferenciaNormativaExtraida,
    usuario,
    motivo: str,
    data_referencia: str = "",
) -> VerificacaoVigencia:
    norma = _norma_do_grupo(termo, referencia)
    if not (motivo or "").strip():
        raise ValueError("Informe o motivo da divergência de vigência.")
    referencia_data = parse_date(data_referencia) if (data_referencia or "").strip() else None
    if (data_referencia or "").strip() and referencia_data is None:
        raise ValueError("A data de referência é inválida.")
    atual = _verificacao_atual(termo, norma)
    return VerificacaoVigencia.objects.create(
        termo=termo,
        norma=norma,
        estado=EstadoVerificacaoVigencia.DIVERGENCIA,
        inicio_vigencia=atual.inicio_vigencia if atual else None,
        fim_vigencia=atual.fim_vigencia if atual else None,
        fonte_documental=atual.fonte_documental if atual else "",
        data_referencia=referencia_data,
        motivo_divergencia=motivo.strip(),
        versao_documento=norma.versao,
        hash_sha256=norma.hash_sha256,
        criado_por=usuario,
        verificado_por=usuario,
        verificado_em=timezone.now(),
    )


def situacao_atual(linha: dict) -> str:
    return f"{_situacao_grupo(linha)}|vigencia_{linha['estado_vigencia']}"

