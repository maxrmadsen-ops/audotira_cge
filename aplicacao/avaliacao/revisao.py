from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.avaliacao.escolhas import (
    AcaoRevisaoCorrespondencia,
    ClassificacaoCorrespondencia,
    MetodoCorrespondencia,
    StatusAvaliacao,
)
from aplicacao.avaliacao.excecoes import ErroAvaliacao, ErroConcorrencia
from aplicacao.avaliacao.executar import _metricas
from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial, RevisaoCorrespondencia
from aplicacao.avaliacao.permissoes import pode_revisar_correspondencia

DESTINO = {
    AcaoRevisaoCorrespondencia.CONFIRMAR: ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO,
    AcaoRevisaoCorrespondencia.REJEITAR: ClassificacaoCorrespondencia.FALSO_POSITIVO,
    AcaoRevisaoCorrespondencia.MARCAR_PARCIAL: ClassificacaoCorrespondencia.CORRESPONDENCIA_PARCIAL,
}


def revisar_correspondencia(correspondencia, usuario, acao, classificacao="", justificativa="", observacao="", versao_esperada=None):
    if not pode_revisar_correspondencia(usuario):
        raise ErroAvaliacao("Somente o auditor pode revisar correspondências.")
    avaliacao = correspondencia.avaliacao
    if avaliacao.status == StatusAvaliacao.CONGELADA:
        raise ErroAvaliacao("Avaliação congelada não pode ser alterada.")
    if correspondencia.classificacao != ClassificacaoCorrespondencia.PENDENTE_REVISAO and acao == AcaoRevisaoCorrespondencia.CONFIRMAR:
        raise ErroAvaliacao("Confirmar só se aplica a correspondência pendente.")
    if acao == AcaoRevisaoCorrespondencia.AJUSTAR:
        if classificacao not in ClassificacaoCorrespondencia.values or classificacao == ClassificacaoCorrespondencia.PENDENTE_REVISAO:
            raise ErroAvaliacao("Informe a classificação ajustada.")
        posterior = classificacao
    elif acao in DESTINO:
        posterior = DESTINO[acao]
        if acao == AcaoRevisaoCorrespondencia.REJEITAR and correspondencia.ground_truth_achado_id and correspondencia.achado_id is None:
            posterior = ClassificacaoCorrespondencia.FALSO_NEGATIVO
    else:
        raise ErroAvaliacao("Ação de revisão não permitida.")
    if posterior == ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO and (
        correspondencia.achado_id is None or correspondencia.ground_truth_achado_id is None
    ):
        raise ErroAvaliacao("Verdadeiro positivo exige achado da análise e achado de referência.")
    with transaction.atomic():
        atual = AvaliacaoInteligenciaArtificial.objects.select_for_update().get(pk=avaliacao.pk)
        if versao_esperada is not None and atual.versao_registro != int(versao_esperada):
            raise ErroConcorrencia("Esta versão foi alterada por outro usuário. Recarregue antes de salvar.")
        if atual.status == StatusAvaliacao.CONGELADA:
            raise ErroAvaliacao("Avaliação congelada não pode ser alterada.")
        anterior = correspondencia.classificacao
        correspondencia.classificacao = posterior
        correspondencia.metodo = MetodoCorrespondencia.REVISAO_HUMANA
        correspondencia.revisao_humana_necessaria = False
        correspondencia.revisado_por = usuario
        correspondencia.revisado_em = timezone.now()
        correspondencia.observacao = observacao
        correspondencia.save()
        RevisaoCorrespondencia.objects.create(
            correspondencia=correspondencia,
            usuario=usuario,
            acao=acao,
            classificacao_anterior=anterior,
            classificacao_posterior=posterior,
            justificativa=justificativa,
            observacao=observacao,
        )
        correspondencias = list(atual.correspondencias.select_related("ground_truth_achado", "achado"))
        comparacoes = list(atual.comparacoes_regra.select_related("regra"))
        execucoes = list(atual.snapshot.execucao_analise.execucoes.select_related("regra"))
        atual.metricas = _metricas(atual, correspondencias, comparacoes, execucoes)
        pendente = any(item.classificacao == ClassificacaoCorrespondencia.PENDENTE_REVISAO for item in correspondencias)
        atual.status = StatusAvaliacao.AGUARDANDO_REVISAO if pendente else StatusAvaliacao.CONCLUIDA
        atual.revisado_por = usuario
        atual.versao_registro += 1
        if atual.status == StatusAvaliacao.CONCLUIDA:
            atual.concluido_em = timezone.now()
        atual.save()
    registrar_evento(
        evento=RegistroAuditoria.Evento.AVALIACAO_IA,
        descricao="Revisão de correspondência.",
        usuario=usuario,
        detalhes={
            "codigo": atual.codigo,
            "acao": "revisao_correspondencia",
            "anterior": anterior,
            "posterior": posterior,
            "correspondencia": correspondencia.pk,
        },
    )
    return correspondencia
