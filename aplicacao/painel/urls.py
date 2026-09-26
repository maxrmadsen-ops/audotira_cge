from django.urls import path

from aplicacao.painel.views import (
    AdministracaoView,
    EntrarView,
    InicioView,
    ModuloIndisponivelView,
    SairView,
    SaudeView,
    viva,
)

app_name = "painel"

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
    path("entrar/", EntrarView.as_view(), name="entrar"),
    path("sair/", SairView.as_view(), name="sair"),
    path("saude/", SaudeView.as_view(), name="saude"),
    path("saude/viva/", viva, name="viva"),
    path("administracao/", AdministracaoView.as_view(), name="administracao"),
    path("modulos/<slug:slug>/", ModuloIndisponivelView.as_view(), name="modulo"),
]
