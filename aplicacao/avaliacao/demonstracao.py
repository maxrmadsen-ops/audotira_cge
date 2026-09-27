"""Ground Truth sintético. Não altera a análise congelada e não chama provedor real."""

from aplicacao.avaliacao.models import GroundTruthPrestacao
from aplicacao.pareceres.escolhas import StatusPreAnalise
from aplicacao.pareceres.models import PreAnaliseTecnica
from aplicacao.usuarios.models import Usuario


def garantir_demonstracao_avaliacao(prestacao, usuario=None):
    existente = GroundTruthPrestacao.objects.filter(prestacao_contas=prestacao, dados_demonstracao=True).order_by("-versao").first()
    if existente is not None:
        return existente
    if usuario is None or usuario.perfil != Usuario.Perfil.AUDITOR:
        return None
    if not PreAnaliseTecnica.objects.filter(prestacao_contas=prestacao, status=StatusPreAnalise.CONGELADA).exists():
        return None
    return None
