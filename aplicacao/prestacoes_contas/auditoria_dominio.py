from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento


def registrar_mutacao(*, usuario, acao: str, instancia, campos: list[str] | None = None, request=None) -> None:
    """Registra criação ou alteração sem gravar o conteúdo dos campos."""
    evento = RegistroAuditoria.Evento.CRIACAO if acao == "criacao" else RegistroAuditoria.Evento.ALTERACAO
    registrar_evento(
        evento=evento,
        descricao=f"{instancia._meta.verbose_name}: {acao}",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", ""),
        detalhes={
            "acao": acao,
            "entidade": instancia._meta.label,
            "identificador": str(instancia.pk),
            "campos": campos or [],
        },
    )
