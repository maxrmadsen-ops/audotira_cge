from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404, JsonResponse
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from aplicacao.painel.navegacao import MODULOS_POR_SLUG
from aplicacao.painel.saude import coletar_saude
from aplicacao.usuarios.acesso import PerfilExigidoMixin
from aplicacao.usuarios.forms import FormularioEntrada
from aplicacao.usuarios.models import Usuario

INDICADORES_FUTUROS = (
    "Prestações analisadas",
    "Em processamento",
    "Aguardando revisão",
    "Regras executadas",
    "Achados",
    "Achados validados",
    "Tempo médio",
    "Economia estimada de esforço",
)


class EntrarView(LoginView):
    template_name = "painel/entrar.html"
    authentication_form = FormularioEntrada
    redirect_authenticated_user = True


class SairView(LogoutView):
    next_page = reverse_lazy("painel:entrar")


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "painel/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["indicadores"] = INDICADORES_FUTUROS
        return contexto


class ModuloIndisponivelView(LoginRequiredMixin, TemplateView):
    template_name = "painel/modulo_indisponivel.html"

    def get_context_data(self, **kwargs):
        slug = self.kwargs["slug"]
        if slug not in MODULOS_POR_SLUG:
            raise Http404("Módulo desconhecido.")
        rotulo, onda = MODULOS_POR_SLUG[slug]
        contexto = super().get_context_data(**kwargs)
        contexto["modulo_rotulo"] = rotulo
        contexto["modulo_onda"] = onda
        return contexto


class AdministracaoView(PerfilExigidoMixin, TemplateView):
    template_name = "painel/administracao.html"
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)


class SaudeView(PerfilExigidoMixin, TemplateView):
    template_name = "painel/saude.html"
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["componentes"] = coletar_saude()
        return contexto


def viva(request):
    return JsonResponse({"aplicacao": "operacional"})
