from django.urls import path

from aplicacao.inteligencia_artificial import prompts_views, views

app_name = "ia"

urlpatterns = [
    path("ia/", views.VisaoGeralIaView.as_view(), name="visao"),
    path("ia/prompts/", prompts_views.ListaPromptsView.as_view(), name="prompts"),
    path("ia/prompts/<slug:codigo>/", prompts_views.DetalhePromptView.as_view(), name="prompt"),
    path("ia/prompts/<slug:codigo>/editar/", prompts_views.EditarPromptView.as_view(), name="editar_prompt"),
    path("ia/prompts/<slug:codigo>/versoes/<int:versao>/ativar/", prompts_views.AtivarPromptView.as_view(), name="ativar_prompt"),
    path("ia/provedores/", views.ProvedoresView.as_view(), name="provedores"),
    path("ia/catalogo/", views.CatalogoIaView.as_view(), name="catalogo"),
    path("ia/roteamento/", views.RoteamentoView.as_view(), name="roteamento"),
    path("ia/consumo/", views.ConsumoView.as_view(), name="consumo"),
    path("ia/laboratorio/", views.LaboratorioView.as_view(), name="laboratorio"),
]
