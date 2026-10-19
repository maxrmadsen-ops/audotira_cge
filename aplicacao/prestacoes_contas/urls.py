from django.urls import include, path
from rest_framework.routers import DefaultRouter

from aplicacao.prestacoes_contas.api import PrestacaoContasViewSet
from aplicacao.prestacoes_contas.views import (
    AtribuirAnalistaView,
    CriarPrestacaoView,
    DetalhePrestacaoView,
    EditarPrestacaoView,
    IncluirContrapartidaView,
    IncluirDespesaView,
    IncluirDevolucaoView,
    IncluirDocumentoView,
    IncluirFuncionarioView,
    IncluirItemView,
    IncluirMetaView,
    IncluirMovimentacaoView,
    IncluirPagamentoView,
    IncluirParcialView,
    IncluirPlanoView,
    ListaPrestacoesView,
)
from aplicacao.prestacoes_contas.revisao_lote import RevisaoLotePlanoView
from aplicacao.prestacoes_contas.revisao_plano import RevisaoPlanoView
from aplicacao.prestacoes_contas.conferencia_despesas import ConferenciaDespesasView, EtapaFuturaView

app_name = "prestacoes_contas"

router = DefaultRouter()
router.register("prestacoes", PrestacaoContasViewSet, basename="prestacao")

urlpatterns = [
    path("prestacoes/", ListaPrestacoesView.as_view(), name="lista"),
    path("prestacoes/nova/", CriarPrestacaoView.as_view(), name="nova"),
    path("prestacoes/<int:pk>/", DetalhePrestacaoView.as_view(), name="detalhe"),
    path("prestacoes/<int:pk>/editar/", EditarPrestacaoView.as_view(), name="editar"),
    path("prestacoes/<int:pk>/atribuir/", AtribuirAnalistaView.as_view(), name="atribuir"),
    path("prestacoes/<int:pk>/plano/", IncluirPlanoView.as_view(), name="incluir_plano"),
    path("prestacoes/<int:pk>/planos/<int:plano_pk>/revisao/", RevisaoPlanoView.as_view(), name="revisao_plano"),
    path("prestacoes/<int:pk>/planos/<int:plano_pk>/revisao-lote/", RevisaoLotePlanoView.as_view(), name="revisao_lote_plano"),
    path("prestacoes/<int:pk>/planos/<int:plano_pk>/conferencia/", ConferenciaDespesasView.as_view(), name="conferencia_despesas"),
    path("prestacoes/<int:pk>/etapa/<slug:slug>/", EtapaFuturaView.as_view(), name="etapa_futura"),
    path("prestacoes/<int:pk>/itens/", IncluirItemView.as_view(), name="incluir_item"),
    path("prestacoes/<int:pk>/metas/", IncluirMetaView.as_view(), name="incluir_meta"),
    path("prestacoes/<int:pk>/parciais/", IncluirParcialView.as_view(), name="incluir_parcial"),
    path("prestacoes/<int:pk>/despesas/", IncluirDespesaView.as_view(), name="incluir_despesa"),
    path("prestacoes/<int:pk>/documentos-fiscais/", IncluirDocumentoView.as_view(), name="incluir_documento"),
    path("prestacoes/<int:pk>/pagamentos/", IncluirPagamentoView.as_view(), name="incluir_pagamento"),
    path("prestacoes/<int:pk>/movimentacoes/", IncluirMovimentacaoView.as_view(), name="incluir_movimentacao"),
    path("prestacoes/<int:pk>/contrapartidas/", IncluirContrapartidaView.as_view(), name="incluir_contrapartida"),
    path("prestacoes/<int:pk>/devolucoes/", IncluirDevolucaoView.as_view(), name="incluir_devolucao"),
    path("prestacoes/<int:pk>/funcionarios/", IncluirFuncionarioView.as_view(), name="incluir_funcionario"),
    path("api/", include(router.urls)),
]
