from django.urls import path

from aplicacao.auditoria.views import ListaRegistrosView

app_name = "auditoria"

urlpatterns = [
    path("registros/", ListaRegistrosView.as_view(), name="registros"),
]
