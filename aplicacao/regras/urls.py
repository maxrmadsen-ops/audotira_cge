from django.urls import path

from aplicacao.regras import views

app_name = "regras"

urlpatterns = [
    path("regras/", views.ListaRegrasView.as_view(), name="lista"),
    path("regras/<str:codigo>/", views.DetalheRegraView.as_view(), name="detalhe"),
    path("prestacoes/<int:pk>/analise/executar/", views.ExecutarAnaliseView.as_view(), name="executar"),
    path("prestacoes/<int:pk>/analise/regras/<str:codigo>/reexecutar/", views.ReexecutarRegraView.as_view(), name="reexecutar"),
    path("analises/<int:pk>/", views.ProgressoAnaliseView.as_view(), name="progresso"),
]
