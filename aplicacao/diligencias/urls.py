from django.urls import path

from aplicacao.diligencias.views import (
    DetalheDiligenciaView,
    EncerrarDiligenciaView,
    NovaDiligenciaView,
    RegistrarRespostaDiligenciaView,
)

app_name = "diligencias"

urlpatterns = [
    path("prestacoes/<int:prestacao_pk>/diligencias/nova/", NovaDiligenciaView.as_view(), name="nova"),
    path("diligencias/<int:pk>/", DetalheDiligenciaView.as_view(), name="detalhe"),
    path("diligencias/<int:pk>/resposta/", RegistrarRespostaDiligenciaView.as_view(), name="resposta"),
    path("diligencias/<int:pk>/encerrar/", EncerrarDiligenciaView.as_view(), name="encerrar"),
]
