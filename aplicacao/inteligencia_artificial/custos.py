from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from aplicacao.inteligencia_artificial.models import PrecoModeloInteligenciaArtificial

SEIS = Decimal("0.000001")


def preco_vigente(modelo, momento=None):
    if modelo is None:
        return None
    dia = momento.date() if hasattr(momento, "date") else (momento or timezone.localdate())
    if isinstance(dia, date):
        referencia = dia
    else:
        referencia = timezone.localdate()
    return (
        PrecoModeloInteligenciaArtificial.objects.filter(modelo=modelo, vigencia_inicio__lte=referencia)
        .filter(Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=referencia))
        .order_by("-vigencia_inicio")
        .first()
    )


def estimar_custo(modelo, tokens_entrada: int, tokens_saida: int, momento=None):
    preco = preco_vigente(modelo, momento)
    if preco is None:
        return None, None, None
    unidade = Decimal(preco.unidade_precificacao)
    entrada = (Decimal(tokens_entrada) / unidade * preco.preco_entrada).quantize(SEIS)
    saida = (Decimal(tokens_saida) / unidade * preco.preco_saida).quantize(SEIS)
    return entrada, saida, (entrada + saida).quantize(SEIS)
