from django.urls import path

from aplicacao.avaliacao.views import (
    AchadoGroundTruthView,
    ConcluirAvaliacaoView,
    CongelarAvaliacaoView,
    CongelarGroundTruthView,
    ContextoGroundTruthView,
    CriarGroundTruthView,
    DetalheAvaliacaoView,
    DetalheGroundTruthView,
    EnviarGroundTruthView,
    FalsoNegativoView,
    IniciarAvaliacaoView,
    ListaAvaliacaoView,
    RegraGroundTruthView,
    RevisarCorrespondenciaView,
    ValidarGroundTruthView,
)

app_name = "avaliacao"

urlpatterns = [
    path("avaliacao/", ListaAvaliacaoView.as_view(), name="lista"),
    path("avaliacao/ground-truth/novo/", CriarGroundTruthView.as_view(), name="criar_ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/", DetalheGroundTruthView.as_view(), name="ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/contexto/", ContextoGroundTruthView.as_view(), name="contexto_ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/regras/", RegraGroundTruthView.as_view(), name="regra_ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/achados/", AchadoGroundTruthView.as_view(), name="achado_ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/enviar/", EnviarGroundTruthView.as_view(), name="enviar_ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/validar/", ValidarGroundTruthView.as_view(), name="validar_ground_truth"),
    path("avaliacao/ground-truth/<int:pk>/congelar/", CongelarGroundTruthView.as_view(), name="congelar_ground_truth"),
    path("avaliacao/iniciar/", IniciarAvaliacaoView.as_view(), name="iniciar"),
    path("avaliacao/<int:pk>/", DetalheAvaliacaoView.as_view(), name="detalhe"),
    path("avaliacao/<int:pk>/correspondencias/<int:correspondencia_pk>/revisar/", RevisarCorrespondenciaView.as_view(), name="revisar"),
    path("avaliacao/<int:pk>/concluir/", ConcluirAvaliacaoView.as_view(), name="concluir"),
    path("avaliacao/<int:pk>/congelar/", CongelarAvaliacaoView.as_view(), name="congelar"),
    path("avaliacao/<int:pk>/falsos-negativos/<int:correspondencia_pk>/", FalsoNegativoView.as_view(), name="falso_negativo"),
]
