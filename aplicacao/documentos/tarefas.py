from celery import shared_task


@shared_task(name="documentos.processar_documento")
def processar_documento_task(documento_id: int, usuario_id: int | None = None, reprocessamento_id: int | None = None) -> None:
    from aplicacao.documentos.servico import executar_pipeline

    executar_pipeline(documento_id, usuario_id=usuario_id, reprocessamento_id=reprocessamento_id)
