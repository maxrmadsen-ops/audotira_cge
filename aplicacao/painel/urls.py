from django.urls import path

from aplicacao.painel.views import (
    AchadosPainelView,
    AdministracaoView,
    DocumentosPainelView,
    EntrarView,
    EvidenciasPainelView,
    FinOpsView,
    IaTecnicoPainelView,
    InicioView,
    ModuloIndisponivelView,
    NormasPainelView,
    OperacaoPainelView,
    PreAnalisePainelView,
    ProcessosPainelView,
    RegrasPainelView,
    RevisaoPainelView,
    SairView,
    SaudeView,
    viva,
)

app_name = "painel"

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
    path("painel/processos/", ProcessosPainelView.as_view(), name="processos"),
    path("painel/documentos/", DocumentosPainelView.as_view(), name="documentos"),
    path("painel/normas/", NormasPainelView.as_view(), name="normas"),
    path("painel/regras/", RegrasPainelView.as_view(), name="regras"),
    path("painel/evidencias/", EvidenciasPainelView.as_view(), name="evidencias"),
    path("painel/achados/", AchadosPainelView.as_view(), name="achados"),
    path("painel/pre-analise/", PreAnalisePainelView.as_view(), name="pre_analise"),
    path("painel/revisao/", RevisaoPainelView.as_view(), name="revisao"),
    path("painel/ia-tecnico/", IaTecnicoPainelView.as_view(), name="ia_tecnico"),
    path("painel/operacao/", OperacaoPainelView.as_view(), name="operacao"),
    path("finops/", FinOpsView.as_view(), name="finops"),
    path("entrar/", EntrarView.as_view(), name="entrar"),
    path("sair/", SairView.as_view(), name="sair"),
    path("saude/", SaudeView.as_view(), name="saude"),
    path("saude/viva/", viva, name="viva"),
    path("administracao/", AdministracaoView.as_view(), name="administracao"),
    path("modulos/<slug:slug>/", ModuloIndisponivelView.as_view(), name="modulo"),
]
