import logging

from celery import shared_task

logger = logging.getLogger("cge.pareceres")


@shared_task(name="pareceres.gerar_pre_analise")
def gerar_pre_analise_task(analise_id: int, usuario_id: int | None = None) -> dict:
    from django.contrib.auth import get_user_model

    from aplicacao.pareceres.gerador import ErroGeracaoPreAnalise, gerar_pre_analise
    from aplicacao.regras.models import ExecucaoAnalise

    usuario = get_user_model().objects.filter(pk=usuario_id).first() if usuario_id else None
    analise = ExecucaoAnalise.objects.select_related("prestacao_contas").get(pk=analise_id)
    try:
        pre = gerar_pre_analise(analise, usuario=usuario)
    except ErroGeracaoPreAnalise as erro:
        logger.info("pre-analise falhou analise=%s", analise_id)
        return {"erro": str(erro)[:300]}
    return {"id": pre.pk, "codigo": pre.codigo, "versao": pre.versao, "status": pre.status}
