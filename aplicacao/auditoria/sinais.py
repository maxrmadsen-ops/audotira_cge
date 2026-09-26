from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento


@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    registrar_evento(
        evento=RegistroAuditoria.Evento.LOGIN,
        descricao="Login realizado.",
        usuario=user,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", ""),
    )


@receiver(user_logged_out)
def registrar_saida(sender, request, user, **kwargs):
    registrar_evento(
        evento=RegistroAuditoria.Evento.SAIDA,
        descricao="Sessão encerrada.",
        usuario=user,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", ""),
    )


@receiver(user_login_failed)
def registrar_falha_login(sender, credentials, request, **kwargs):
    usuario_informado = str(credentials.get("username", ""))[:150]
    registrar_evento(
        evento=RegistroAuditoria.Evento.FALHA_LOGIN,
        descricao="Tentativa de login sem sucesso.",
        usuario=None,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", ""),
        detalhes={"usuario_informado": usuario_informado},
    )
