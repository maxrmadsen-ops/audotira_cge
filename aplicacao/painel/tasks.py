"""Tarefa periódica da fundação. O nome do módulo segue o contrato do Celery."""

import logging

from celery import shared_task

logger = logging.getLogger("celery")


@shared_task(name="painel.verificar_operacionalidade")
def verificar_operacionalidade() -> str:
    logger.info("Verificação periódica da fundação executada.")
    return "ok"
