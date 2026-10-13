from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.diligencias.escolhas import SituacaoDiligencia
from aplicacao.diligencias.models import Diligencia, HistoricoDiligencia
from aplicacao.usuarios.acesso import exigir_atuar_na_prestacao


def _proximo_identificador(prestacao) -> str:
    sequencia = Diligencia.objects.filter(prestacao=prestacao).count() + 1
    return f"DIL-{prestacao.pk:04d}-{sequencia:03d}"


def abrir_diligencia(
    *,
    prestacao,
    usuario,
    motivo: str,
    descricao: str,
    prazo=None,
    documentos=None,
    request=None,
) -> Diligencia:
    exigir_atuar_na_prestacao(usuario, prestacao)
    with transaction.atomic():
        diligencia = Diligencia.objects.create(
            identificador=_proximo_identificador(prestacao),
            prestacao=prestacao,
            solicitante=usuario,
            motivo=motivo,
            descricao=descricao.strip(),
            prazo=prazo,
            situacao=SituacaoDiligencia.ABERTA,
            demonstracao=prestacao.demonstracao,
        )
        if documentos:
            diligencia.documentos.set(documentos)
        HistoricoDiligencia.objects.create(
            diligencia=diligencia,
            usuario=usuario,
            situacao_anterior="",
            situacao_nova=SituacaoDiligencia.ABERTA,
            observacao="Abertura da diligência",
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.ABERTURA_DILIGENCIA,
        descricao=f"Diligência {diligencia.identificador} aberta",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", "") if request else "",
        detalhes={
            "diligencia_id": diligencia.pk,
            "identificador": diligencia.identificador,
            "prestacao_id": prestacao.pk,
            "motivo": motivo,
        },
    )
    return diligencia


def registrar_resposta_diligencia(*, diligencia: Diligencia, usuario, resposta: str, request=None) -> Diligencia:
    """Registra manifestação informada. Não inventa resposta do beneficiário."""
    exigir_atuar_na_prestacao(usuario, diligencia.prestacao)
    texto = (resposta or "").strip()
    if not texto:
        raise ValueError("Informe a resposta/manifestação recebida.")
    anterior = diligencia.situacao
    diligencia.resposta = texto
    diligencia.respondida_em = timezone.now()
    diligencia.situacao = SituacaoDiligencia.RESPONDIDA
    diligencia.save(update_fields=["resposta", "respondida_em", "situacao", "atualizado_em"])
    HistoricoDiligencia.objects.create(
        diligencia=diligencia,
        usuario=usuario,
        situacao_anterior=anterior,
        situacao_nova=SituacaoDiligencia.RESPONDIDA,
        observacao="Registro da resposta informada",
    )
    registrar_evento(
        evento=RegistroAuditoria.Evento.ALTERACAO_DILIGENCIA,
        descricao=f"Resposta registrada na diligência {diligencia.identificador}",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", "") if request else "",
        detalhes={"diligencia_id": diligencia.pk, "situacao": diligencia.situacao},
    )
    return diligencia


def encerrar_diligencia(*, diligencia: Diligencia, usuario, observacao: str = "", request=None) -> Diligencia:
    exigir_atuar_na_prestacao(usuario, diligencia.prestacao)
    anterior = diligencia.situacao
    diligencia.situacao = SituacaoDiligencia.ENCERRADA
    diligencia.encerrada_por = usuario
    diligencia.encerrada_em = timezone.now()
    diligencia.save(update_fields=["situacao", "encerrada_por", "encerrada_em", "atualizado_em"])
    HistoricoDiligencia.objects.create(
        diligencia=diligencia,
        usuario=usuario,
        situacao_anterior=anterior,
        situacao_nova=SituacaoDiligencia.ENCERRADA,
        observacao=observacao.strip() or "Encerramento",
    )
    registrar_evento(
        evento=RegistroAuditoria.Evento.ALTERACAO_DILIGENCIA,
        descricao=f"Diligência {diligencia.identificador} encerrada",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", "") if request else "",
        detalhes={"diligencia_id": diligencia.pk, "situacao": diligencia.situacao},
    )
    return diligencia
