"""Revisão humana da pré-análise. Não cria Ground Truth."""

from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.pareceres.escolhas import AcaoRevisaoPreAnalise, OrigemConteudo, StatusPreAnalise, StatusValidacaoAfirmacao
from aplicacao.pareceres.models import RevisaoPreAnalise
from aplicacao.usuarios.acesso import pode_executar_analise, pode_validar_analise


class ErroRevisaoPreAnalise(Exception):
    pass


class ErroConcorrencia(ErroRevisaoPreAnalise):
    pass


def revisar_afirmacao(pre, afirmacao, usuario, acao, texto="", justificativa="", versao_esperada=None):
    if not pode_executar_analise(usuario):
        raise ErroRevisaoPreAnalise("Perfil sem permissão para revisar a pré-análise.")
    if pre.status == StatusPreAnalise.CONGELADA:
        raise ErroRevisaoPreAnalise("Versão congelada não pode ser alterada.")
    if afirmacao.secao.pre_analise_id != pre.pk:
        raise ErroRevisaoPreAnalise("A afirmação não pertence a esta versão.")
    with transaction.atomic():
        pre = type(pre).objects.select_for_update().get(pk=pre.pk)
        if versao_esperada is not None and pre.versao_registro != int(versao_esperada):
            raise ErroConcorrencia("Esta versão foi alterada por outro usuário. Recarregue antes de salvar.")
        anterior = afirmacao.texto_atual
        if acao == AcaoRevisaoPreAnalise.ACEITAR:
            posterior = anterior
        elif acao == AcaoRevisaoPreAnalise.AJUSTAR:
            posterior = (texto or "").strip()
            if not posterior:
                raise ErroRevisaoPreAnalise("O ajuste precisa de texto.")
            afirmacao.texto_atual = posterior
            afirmacao.alterada_por_humano = True
            afirmacao.origem_conteudo = OrigemConteudo.HUMANO
        elif acao == AcaoRevisaoPreAnalise.REJEITAR:
            posterior = anterior
            afirmacao.exibir_oficial = False
            afirmacao.status_validacao = StatusValidacaoAfirmacao.REJEITADA
            afirmacao.alterada_por_humano = True
        else:
            raise ErroRevisaoPreAnalise("Ação de revisão não permitida.")
        afirmacao.save()
        pre.status = StatusPreAnalise.EM_REVISAO if acao != AcaoRevisaoPreAnalise.ACEITAR else pre.status
        if acao == AcaoRevisaoPreAnalise.ACEITAR and pre.status == StatusPreAnalise.AGUARDANDO_REVISAO:
            pre.status = StatusPreAnalise.EM_REVISAO
        pre.revisada_por = usuario
        pre.revisada_em = timezone.now()
        pre.versao_registro += 1
        pre.save()
        RevisaoPreAnalise.objects.create(
            pre_analise=pre,
            afirmacao=afirmacao,
            acao=acao,
            texto_anterior=anterior,
            texto_posterior=posterior,
            justificativa=justificativa,
            usuario=usuario,
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.REVISAO_HUMANA,
        descricao="Revisão de afirmação da pré-análise.",
        usuario=usuario,
        detalhes={"codigo": pre.codigo, "acao": acao, "afirmacao": afirmacao.pk},
    )
    return pre


def congelar(pre, usuario):
    from aplicacao.pareceres.hash_conteudo import calcular_hash

    if not pode_validar_analise(usuario):
        raise ErroRevisaoPreAnalise("Somente auditor ou administrador pode congelar a pré-análise.")
    if pre.status == StatusPreAnalise.CONGELADA:
        raise ErroRevisaoPreAnalise("A versão já está congelada.")
    if pre.status == StatusPreAnalise.ERRO:
        raise ErroRevisaoPreAnalise("Versão com erro não pode ser congelada.")
    with transaction.atomic():
        pre = type(pre).objects.select_for_update().get(pk=pre.pk)
        pre.hash_conteudo = calcular_hash(pre)
        pre.status = StatusPreAnalise.CONGELADA
        pre.congelada_por = usuario
        pre.congelada_em = timezone.now()
        pre.versao_registro += 1
        pre.save()
        RevisaoPreAnalise.objects.create(
            pre_analise=pre,
            acao=AcaoRevisaoPreAnalise.CONGELAR,
            texto_anterior="",
            texto_posterior=pre.hash_conteudo,
            usuario=usuario,
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.GERACAO_PRE_ANALISE,
        descricao="Congelamento da pré-análise.",
        usuario=usuario,
        detalhes={"codigo": pre.codigo, "versao": pre.versao, "fase": "congelamento"},
    )
    return pre
