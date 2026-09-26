import logging

from aplicacao.auditoria.models import RegistroAuditoria

logger = logging.getLogger("cge.auditoria")


def obter_ip(request) -> str | None:
    if request is None:
        return None
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def registrar_evento(
    *,
    evento: str,
    descricao: str = "",
    usuario=None,
    endereco_ip: str | None = None,
    caminho: str = "",
    detalhes: dict | None = None,
) -> RegistroAuditoria:
    registro = RegistroAuditoria.objects.create(
        evento=evento,
        descricao=descricao,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        endereco_ip=endereco_ip or None,
        caminho=caminho[:255],
        detalhes=detalhes or {},
    )
    logger.info(
        "evento=%s usuario=%s caminho=%s",
        evento,
        getattr(usuario, "username", None),
        caminho,
    )
    return registro
