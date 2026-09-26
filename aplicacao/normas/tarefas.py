from celery import shared_task


@shared_task(name="normas.processar_norma")
def processar_norma_task(norma_id: int, usuario_id: int | None = None, reprocessamento_id: int | None = None) -> None:
    from aplicacao.normas.servico import executar_pipeline

    executar_pipeline(norma_id, usuario_id=usuario_id, reprocessamento_id=reprocessamento_id)
