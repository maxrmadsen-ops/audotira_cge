"""Pré-análise sintética. Não cria versão se a prestação ainda não tem achados."""

from aplicacao.pareceres.gerador import gerar_pre_analise
from aplicacao.pareceres.models import PreAnaliseTecnica


def garantir_demonstracao_pre_analise(prestacao):
    if not prestacao.achados.exists():
        return None
    analise = prestacao.execucoes_analise.order_by("-id").first()
    if analise is None:
        return None
    existente = PreAnaliseTecnica.objects.filter(prestacao_contas=prestacao, execucao_analise=analise, demonstracao=True).order_by("-versao").first()
    if existente is not None:
        return existente
    return gerar_pre_analise(analise, demonstracao=True)
