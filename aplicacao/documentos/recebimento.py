from django.db.models import Count, Q, Sum

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.documentos.armazenamento import armazenar_pdf
from aplicacao.documentos.escolhas import OrigemDocumento, StatusProcessamento, TipoDocumento
from aplicacao.documentos.models import Documento
from aplicacao.documentos.tarefas import processar_documento_task
from aplicacao.documentos.validacao import validar_envio


def receber_arquivo(*, prestacao, arquivo, usuario, parcial=None, request=None) -> tuple[Documento, list[int]]:
    conteudo = arquivo.read()
    dados = validar_envio(arquivo.name, conteudo, arquivo.content_type or "")
    duplicados = list(
        Documento.objects.ativos()
        .filter(hash_sha256=dados["hash_sha256"])
        .exclude(prestacao_contas=prestacao)
        .values_list("pk", flat=True)[:5]
    )
    mesmo_contexto = list(
        Documento.objects.ativos()
        .filter(hash_sha256=dados["hash_sha256"], prestacao_contas=prestacao)
        .values_list("pk", flat=True)[:5]
    )
    relativo = armazenar_pdf(prestacao.pk, conteudo)
    documento = Documento.objects.create(
        prestacao_contas=prestacao,
        prestacao_parcial=parcial,
        nome_original=(arquivo.name or "documento.pdf")[:255],
        nome_armazenado=relativo,
        mime_type=dados["mime_type"],
        extensao=dados["extensao"],
        tamanho_bytes=dados["tamanho_bytes"],
        hash_sha256=dados["hash_sha256"],
        origem=OrigemDocumento.DEMONSTRACAO if prestacao.demonstracao else OrigemDocumento.UPLOAD,
        demonstracao=prestacao.demonstracao,
        criado_por=usuario,
        status_processamento=StatusProcessamento.RECEBIDO,
    )
    registrar_evento(
        evento=RegistroAuditoria.Evento.UPLOAD,
        descricao="Upload de documento",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", ""),
        detalhes={
            "documento": documento.pk,
            "prestacao": prestacao.pk,
            "hash_sha256": dados["hash_sha256"],
            "tamanho_bytes": dados["tamanho_bytes"],
            "duplicados": duplicados + mesmo_contexto,
        },
    )
    processar_documento_task.delay(documento.pk, getattr(usuario, "pk", None))
    return documento, duplicados + mesmo_contexto


def indicadores(consulta):
    agregados = consulta.aggregate(paginas=Sum("quantidade_paginas"))
    return {
        "total": consulta.count(),
        "paginas": agregados["paginas"] or 0,
        "processados": consulta.filter(
            status_processamento__in=[
                StatusProcessamento.PROCESSADO,
                StatusProcessamento.AGUARDANDO_VALIDACAO,
                StatusProcessamento.VALIDADO,
            ]
        ).count(),
        "aguardando_validacao": consulta.filter(status_processamento=StatusProcessamento.AGUARDANDO_VALIDACAO).count(),
        "com_ocr": consulta.filter(paginas__necessitou_ocr=True).distinct().count(),
        "com_erro": consulta.filter(status_processamento=StatusProcessamento.ERRO).count(),
        "nao_classificados": consulta.filter(tipo_documento=TipoDocumento.NAO_CLASSIFICADO).count(),
    }


def filtrar_documentos(consulta, parametros):
    termo = parametros.get("q", "").strip()
    tipo = parametros.get("tipo", "").strip()
    status = parametros.get("status", "").strip()
    parcial = parametros.get("parcial", "").strip()
    if termo:
        consulta = consulta.filter(Q(nome_original__icontains=termo) | Q(subtipo_documento__icontains=termo))
    if tipo:
        consulta = consulta.filter(tipo_documento=tipo)
    if status:
        consulta = consulta.filter(status_processamento=status)
    if parcial:
        consulta = consulta.filter(prestacao_parcial_id=parcial)
    return consulta.select_related("prestacao_parcial", "prestacao_contas").annotate(ocr=Count("paginas", filter=Q(paginas__necessitou_ocr=True)))
