from celery import shared_task

from aplicacao.regras.motor import executar_analise


@shared_task(name="regras.executar_analise")
def executar_analise_task(analise_id: int) -> int:
    executar_analise(analise_id)
    return analise_id
