from django.contrib.auth import get_user_model

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.documentos.armazenamento import ler_arquivo
from aplicacao.documentos.classificacao import classificar
from aplicacao.documentos.escolhas import EtapaProcessamento, StatusProcessamento
from aplicacao.documentos.extracao import ErroExtracao, ExtratorPDF
from aplicacao.documentos.metadados import extrair_candidatos
from aplicacao.documentos.models import DadoExtraidoDocumento, Documento, PaginaDocumento, ReprocessamentoDocumento


def executar_pipeline(documento_id: int, usuario_id: int | None = None, reprocessamento_id: int | None = None) -> None:
    documento = Documento.objects.get(pk=documento_id)
    usuario = get_user_model().objects.filter(pk=usuario_id).first() if usuario_id else None
    try:
        _marcar(documento, StatusProcessamento.VALIDANDO, EtapaProcessamento.VALIDANDO_ARQUIVO, "")
        caminho = ler_arquivo(documento.nome_armazenado)
        _marcar(documento, StatusProcessamento.PROCESSANDO, EtapaProcessamento.EXTRAINDO_TEXTO)
        extrator = ExtratorPDF()
        paginas = extrator.extrair(caminho)
        if any(pagina["necessitou_ocr"] for pagina in paginas):
            _marcar(documento, etapa=EtapaProcessamento.EXECUTANDO_OCR)
        _substituir_paginas(documento, paginas)
        _marcar(documento, etapa=EtapaProcessamento.CLASSIFICANDO)
        texto = "\n".join(pagina.texto_extraido for pagina in documento.paginas.all())
        sugestao = classificar(documento.nome_original, texto)
        _aplicar_sugestao(documento, sugestao)
        _marcar(documento, etapa=EtapaProcessamento.EXTRAINDO_METADADOS)
        _substituir_dados(documento)
        if documento.classificacao_validada:
            _marcar(documento, StatusProcessamento.VALIDADO, EtapaProcessamento.CONCLUIDO, "")
            resultado = "sucesso"
        else:
            _marcar(documento, StatusProcessamento.AGUARDANDO_VALIDACAO, EtapaProcessamento.AGUARDANDO_VALIDACAO, "")
            resultado = "sucesso"
        registrar_evento(
            evento=RegistroAuditoria.Evento.PROCESSAMENTO,
            descricao="Processamento documental concluído",
            usuario=usuario,
            detalhes={"documento": documento.pk, "paginas": documento.quantidade_paginas, "resultado": resultado},
        )
    except ErroExtracao as exc:
        _falhar(documento, usuario, exc.mensagem, reprocessamento_id)
        return
    except Exception:
        _falhar(documento, usuario, "Falha inesperada no processamento do documento.", reprocessamento_id)
        return
    if reprocessamento_id:
        ReprocessamentoDocumento.objects.filter(pk=reprocessamento_id).update(
            resultado="sucesso",
            detalhe=f"{documento.quantidade_paginas or 0} páginas",
        )


def _marcar(documento: Documento, status: str | None = None, etapa: str | None = None, erro: str | None = None) -> None:
    campos = ["atualizado_em"]
    if status:
        documento.status_processamento = status
        campos.append("status_processamento")
    if etapa:
        documento.etapa = etapa
        campos.append("etapa")
    if erro is not None:
        documento.erro_processamento = erro
        campos.append("erro_processamento")
    documento.save(update_fields=campos)


def _substituir_paginas(documento: Documento, paginas: list[dict]) -> None:
    documento.paginas.all().delete()
    documento.dados_extraidos.all().delete()
    PaginaDocumento.objects.bulk_create(
        [
            PaginaDocumento(
                documento=documento,
                numero_pagina=pagina["numero_pagina"],
                texto_extraido=pagina["texto_extraido"],
                metodo_extracao=pagina["metodo_extracao"],
                qualidade_extracao=pagina["qualidade_extracao"],
                necessitou_ocr=pagina["necessitou_ocr"],
                ocr_executado=pagina["ocr_executado"],
                quantidade_caracteres=pagina["quantidade_caracteres"],
                dados_posicionais=pagina["dados_posicionais"],
                erro_ocr=pagina["erro_ocr"],
            )
            for pagina in paginas
        ]
    )
    documento.quantidade_paginas = len(paginas)
    documento.save(update_fields=["quantidade_paginas", "atualizado_em"])


def _aplicar_sugestao(documento: Documento, sugestao: dict) -> None:
    documento.tipo_sugerido = sugestao["tipo"]
    documento.metodo_classificacao = sugestao["metodo"]
    documento.confianca_classificacao = sugestao["confianca"]
    if not documento.classificacao_original:
        documento.classificacao_original = sugestao["tipo"]
    if not documento.classificacao_validada:
        documento.tipo_documento = sugestao["tipo"]
    documento.save(
        update_fields=[
            "tipo_sugerido",
            "metodo_classificacao",
            "confianca_classificacao",
            "classificacao_original",
            "tipo_documento",
            "atualizado_em",
        ]
    )


def _substituir_dados(documento: Documento) -> None:
    documento.dados_extraidos.all().delete()
    paginas = list(documento.paginas.all())
    por_numero = {pagina.numero_pagina: pagina for pagina in paginas}
    DadoExtraidoDocumento.objects.bulk_create(
        [
            DadoExtraidoDocumento(
                documento=documento,
                pagina=por_numero.get(item["numero_pagina"]),
                tipo=item["tipo"],
                valor=item["valor"],
                trecho=item["trecho"],
                metodo=item["metodo"],
                confianca=item["confianca"],
            )
            for item in extrair_candidatos(paginas)
        ]
    )


def _falhar(documento: Documento, usuario, mensagem: str, reprocessamento_id: int | None) -> None:
    _marcar(documento, StatusProcessamento.ERRO, EtapaProcessamento.ERRO, mensagem[:500])
    registrar_evento(
        evento=RegistroAuditoria.Evento.ERRO_PROCESSAMENTO,
        descricao="Falha no processamento documental",
        usuario=usuario,
        detalhes={"documento": documento.pk, "erro": mensagem[:180]},
    )
    if reprocessamento_id:
        ReprocessamentoDocumento.objects.filter(pk=reprocessamento_id).update(resultado="erro", detalhe=mensagem[:255])
