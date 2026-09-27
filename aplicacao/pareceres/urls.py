from django.urls import path

from aplicacao.pareceres.views import DetalhePreAnaliseView, ExportarPreAnaliseView, GerarPreAnaliseView, ListaPreAnalisesView

app_name = "pareceres"

urlpatterns = [
    path("pre-analises/", ListaPreAnalisesView.as_view(), name="lista"),
    path("pre-analises/<int:pk>/", DetalhePreAnaliseView.as_view(), name="detalhe"),
    path("pre-analises/<int:pk>/exportar/", ExportarPreAnaliseView.as_view(), name="exportar"),
    path("prestacoes/<int:prestacao_pk>/pre-analise/gerar/", GerarPreAnaliseView.as_view(), name="gerar"),
]
