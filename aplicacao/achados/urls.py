from django.urls import path

from aplicacao.achados.api import AchadoViewSet, EvidenciaViewSet
from aplicacao.achados.views import DetalheAchadoView, ListaAchadosView

app_name = "achados"

urlpatterns = [
    path("achados/", ListaAchadosView.as_view(), name="lista"),
    path("achados/<int:pk>/", DetalheAchadoView.as_view(), name="detalhe"),
    path("api/evidencias/", EvidenciaViewSet.as_view({"get": "list"}), name="api_evidencias"),
    path("api/evidencias/<int:pk>/", EvidenciaViewSet.as_view({"get": "retrieve"}), name="api_evidencia"),
    path("api/achados/", AchadoViewSet.as_view({"get": "list"}), name="api_achados"),
    path("api/achados/<int:pk>/", AchadoViewSet.as_view({"get": "retrieve"}), name="api_achado"),
    path("api/achados/<int:pk>/evidencias/", AchadoViewSet.as_view({"get": "evidencias"}), name="api_achado_evidencias"),
    path("api/achados/<int:pk>/revisoes/", AchadoViewSet.as_view({"get": "revisoes", "post": "revisoes"}), name="api_achado_revisoes"),
]
