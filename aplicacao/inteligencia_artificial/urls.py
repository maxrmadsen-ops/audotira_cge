from django.urls import path

from aplicacao.inteligencia_artificial import views

app_name = "ia"

urlpatterns = [
    path("ia/provedores/", views.ProvedoresView.as_view(), name="provedores"),
    path("ia/catalogo/", views.CatalogoIaView.as_view(), name="catalogo"),
    path("ia/roteamento/", views.RoteamentoView.as_view(), name="roteamento"),
    path("ia/consumo/", views.ConsumoView.as_view(), name="consumo"),
    path("ia/laboratorio/", views.LaboratorioView.as_view(), name="laboratorio"),
]
