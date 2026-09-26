from django.urls import path

from aplicacao.normas import views

app_name = "normas"

urlpatterns = [
    path("normas/", views.ListaNormasView.as_view(), name="lista"),
    path("normas/nova/", views.CriarNormaView.as_view(), name="criar"),
    path("normas/pesquisa/", views.PesquisaNormativaView.as_view(), name="pesquisa"),
    path("normas/pesquisa/<int:pk>/", views.ConsultaNormativaView.as_view(), name="consulta"),
    path("normas/<int:pk>/", views.DetalheNormaView.as_view(), name="detalhe"),
    path("normas/<int:pk>/editar/", views.EditarNormaView.as_view(), name="editar"),
    path("normas/<int:pk>/arquivo/", views.ArquivoNormaView.as_view(), name="arquivo"),
    path("normas/<int:pk>/nova-versao/", views.NovaVersaoView.as_view(), name="nova_versao"),
    path("normas/<int:pk>/reprocessar/", views.ReprocessarNormaView.as_view(), name="reprocessar"),
    path("normas/<int:pk>/desativar/", views.DesativarNormaView.as_view(), name="desativar"),
    path("normas/<int:pk>/aplicabilidade/", views.AplicabilidadeView.as_view(), name="aplicabilidade"),
    path("normas/<int:pk>/relacionamento/", views.RelacionamentoView.as_view(), name="relacionamento"),
]
