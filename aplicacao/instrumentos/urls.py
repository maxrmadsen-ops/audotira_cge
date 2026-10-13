from django.urls import path

from aplicacao.instrumentos.views_preparacao import BaseNormativaView, InstrumentoParceriaView, PreparacaoAnaliseView

app_name = "instrumentos"

urlpatterns = [
    path("prestacoes/<int:pk>/preparacao/", PreparacaoAnaliseView.as_view(), name="preparacao"),
    path("prestacoes/<int:pk>/preparacao/instrumento/", InstrumentoParceriaView.as_view(), name="instrumento"),
    path("prestacoes/<int:pk>/preparacao/base-normativa/", BaseNormativaView.as_view(), name="base_normativa"),
]
