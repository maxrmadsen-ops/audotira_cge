from django.urls import path

from aplicacao.laboratorio import views

app_name = "laboratorio"

urlpatterns = [
    path("prestacoes/<int:pk>/laboratorio/", views.LaboratorioProcessoView.as_view(), name="processo"),
    path("laboratorio/lotes/<int:lote_pk>/", views.LaboratorioLoteView.as_view(), name="lote"),
    path("laboratorio/lotes/<int:lote_pk>/curadoria/", views.LaboratorioCuradoriaView.as_view(), name="curadoria"),
    path("laboratorio/lotes/<int:lote_pk>/relatorio/", views.RelatorioLaboratorioView.as_view(), name="relatorio"),
    path("laboratorio/lotes/<int:lote_pk>/conciliacao/", views.ConciliacaoFinanceiraView.as_view(), name="conciliacao"),
    path(
        "laboratorio/lotes/<int:lote_pk>/conciliacao/<int:cadeia_pk>/revisar/",
        views.RevisarCadeiaView.as_view(),
        name="revisar_cadeia",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/regioes/<int:regiao_pk>/revisar/",
        views.RevisarRegiaoView.as_view(),
        name="revisar_regiao",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/regioes/<int:regiao_pk>/ajustar/",
        views.AjustarRegiaoView.as_view(),
        name="ajustar_regiao",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/campos/<int:campo_pk>/revisar/",
        views.RevisarCampoView.as_view(),
        name="revisar_campo",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/rubricas/<int:rubrica_pk>/revisar/",
        views.RevisarRubricaView.as_view(),
        name="revisar_rubrica",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/vinculos/<int:vinculo_pk>/revisar/",
        views.RevisarVinculoView.as_view(),
        name="revisar_vinculo",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/pendencias/",
        views.CriarPendenciaView.as_view(),
        name="criar_pendencia",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/paginas/<int:pagina_pk>/ilegivel/",
        views.MarcarIlegivelView.as_view(),
        name="marcar_ilegivel",
    ),
    path(
        "laboratorio/lotes/<int:lote_pk>/reprocessar/",
        views.SolicitarReprocessamentoView.as_view(),
        name="reprocessar",
    ),
]
