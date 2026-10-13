"""Serviço de atribuição/redistribuição do analista responsável."""

from django.core.exceptions import ValidationError
from django.db import transaction

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.prestacoes_contas.models import HistoricoAtribuicaoPrestacao, PrestacaoContas
from aplicacao.usuarios.acesso import pode_distribuir_processos
from aplicacao.usuarios.models import Usuario


def atribuir_analista(
    *,
    prestacao: PrestacaoContas,
    analista_novo: Usuario | None,
    alterado_por: Usuario,
    justificativa: str = "",
    request=None,
) -> HistoricoAtribuicaoPrestacao:
    if not pode_distribuir_processos(alterado_por):
        raise ValidationError("Somente Administrador ou Auditor pode distribuir processos.")
    if analista_novo is not None:
        if analista_novo.perfil != Usuario.Perfil.ANALISTA or not analista_novo.is_active:
            raise ValidationError("O responsável deve ser um analista ativo.")

    anterior = prestacao.analista_responsavel
    if anterior and analista_novo and anterior.pk == analista_novo.pk:
        raise ValidationError("O analista informado já é o responsável pelo processo.")

    with transaction.atomic():
        historico = HistoricoAtribuicaoPrestacao.objects.create(
            prestacao=prestacao,
            analista_anterior=anterior,
            analista_novo=analista_novo,
            alterado_por=alterado_por,
            justificativa=(justificativa or "").strip(),
        )
        prestacao.analista_responsavel = analista_novo
        prestacao.save(update_fields=["analista_responsavel", "atualizado_em"])

    redistribuicao = anterior is not None
    registrar_evento(
        evento=(
            RegistroAuditoria.Evento.REDISTRIBUICAO_PROCESSO
            if redistribuicao
            else RegistroAuditoria.Evento.ATRIBUICAO_PROCESSO
        ),
        descricao=(
            f"{'Redistribuição' if redistribuicao else 'Atribuição'} do processo "
            f"{prestacao.numero_processo}"
        ),
        usuario=alterado_por,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", "") if request else "",
        detalhes={
            "prestacao_id": prestacao.pk,
            "numero_processo": prestacao.numero_processo,
            "analista_anterior_id": anterior.pk if anterior else None,
            "analista_anterior": anterior.username if anterior else None,
            "analista_novo_id": analista_novo.pk if analista_novo else None,
            "analista_novo": analista_novo.username if analista_novo else None,
            "justificativa": (justificativa or "").strip(),
            "historico_id": historico.pk,
        },
    )
    return historico
