import logging

from celery import shared_task

logger = logging.getLogger("cge.avaliacao")


@shared_task(name="avaliacao.executar_avaliacao")
def executar_avaliacao_task(avaliacao_id: int, usuario_id: int | None = None) -> dict:
    from django.contrib.auth import get_user_model

    from aplicacao.avaliacao.excecoes import ErroAvaliacao
    from aplicacao.avaliacao.executar import executar_comparacao
    from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial

    usuario = get_user_model().objects.filter(pk=usuario_id).first() if usuario_id else None
    avaliacao = AvaliacaoInteligenciaArtificial.objects.select_related("ground_truth", "snapshot", "snapshot__pre_analise").get(pk=avaliacao_id)
    try:
        avaliacao = executar_comparacao(avaliacao, usuario=usuario)
    except ErroAvaliacao as erro:
        logger.info("avaliacao falhou id=%s", avaliacao_id)
        return {"erro": str(erro)[:300], "status": avaliacao.status}
    return {"id": avaliacao.pk, "codigo": avaliacao.codigo, "status": avaliacao.status}
