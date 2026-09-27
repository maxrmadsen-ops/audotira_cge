import logging

from celery import shared_task

from aplicacao.achados.gerador import gerar_achados

logger = logging.getLogger("cge.achados")


@shared_task(name="achados.gerar_achados")
def gerar_achados_task(analise_id: int) -> dict:
    resumo = gerar_achados(analise_id)
    logger.info(
        "analise=%s candidatos=%s consolidados=%s achados=%s erros=%s",
        analise_id,
        resumo.candidatos,
        resumo.consolidados,
        resumo.achados,
        len(resumo.erros),
    )
    return {
        "candidatos": resumo.candidatos,
        "consolidados": resumo.consolidados,
        "achados": resumo.achados,
        "erros": resumo.erros,
    }
