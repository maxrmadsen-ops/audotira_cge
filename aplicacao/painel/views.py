from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404, JsonResponse
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.painel.consultas.filtros import FiltrosPainel
from aplicacao.painel.consultas.finops import montar_finops
from aplicacao.painel.consultas.abas import (
    montar_achados,
    montar_documentos,
    montar_evidencias,
    montar_ia_tecnico,
    montar_normas,
    montar_operacao,
    montar_pre_analise,
    montar_processos,
    montar_regras,
    montar_revisao,
)
from aplicacao.painel.consultas.visao import descrever_campos, montar_visao, opcoes_de_filtro
from aplicacao.painel.navegacao import MODULOS_POR_SLUG
from aplicacao.painel.saude import coletar_saude
from aplicacao.usuarios.acesso import PerfilExigidoMixin
from aplicacao.usuarios.forms import FormularioEntrada
from aplicacao.usuarios.models import Usuario

MONTADORES = {
    "visao": montar_visao,
    "processos": montar_processos,
    "documentos": montar_documentos,
    "normas": montar_normas,
    "regras": montar_regras,
    "evidencias": montar_evidencias,
    "achados": montar_achados,
    "pre_analise": montar_pre_analise,
    "revisao": montar_revisao,
    "ia_tecnico": montar_ia_tecnico,
    "operacao": montar_operacao,
}

ABAS_PAINEL = (
    ("visao", "Visão 360°", "painel:inicio"),
    ("processos", "Processos", "painel:processos"),
    ("documentos", "Documentos", "painel:documentos"),
    ("normas", "Normas & Referenciais", "painel:normas"),
    ("regras", "Regras & Verificações", "painel:regras"),
    ("evidencias", "Evidências", "painel:evidencias"),
    ("achados", "Achados", "painel:achados"),
    ("pre_analise", "Pré-Análise", "painel:pre_analise"),
    ("revisao", "Revisão Humana", "painel:revisao"),
    ("ia_tecnico", "IA × Técnico", "painel:ia_tecnico"),
    ("operacao", "Operação & IA", "painel:operacao"),
)


class EntrarView(LoginView):
    template_name = "painel/entrar.html"
    authentication_form = FormularioEntrada
    redirect_authenticated_user = True


class SairView(LogoutView):
    next_page = reverse_lazy("painel:entrar")


class CentralAnaliticaView(LoginRequiredMixin, TemplateView):
    template_name = "painel/central.html"
    aba = "visao"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtros = FiltrosPainel.da_requisicao(self.request.GET)
        contexto["aba_atual"] = self.aba
        contexto["abas_painel"] = ABAS_PAINEL
        contexto["filtros"] = filtros
        opcoes = opcoes_de_filtro(self.aba, filtros.origem)
        contexto["campos_filtro"] = descrever_campos(self.aba, filtros, opcoes)
        contexto["painel"] = MONTADORES[self.aba](filtros)
        if self.aba == "visao":
            hoje = timezone.localdate()
            contexto["janelas"] = [
                (rotulo, filtros.alterar(inicio=hoje - timedelta(days=dias), fim=hoje).querystring())
                for rotulo, dias in (("30d", 30), ("90d", 90), ("12m", 365))
            ]
        return contexto


class InicioView(CentralAnaliticaView):
    aba = "visao"


class ProcessosPainelView(CentralAnaliticaView):
    aba = "processos"


class DocumentosPainelView(CentralAnaliticaView):
    aba = "documentos"


class NormasPainelView(CentralAnaliticaView):
    aba = "normas"


class RegrasPainelView(CentralAnaliticaView):
    aba = "regras"


class EvidenciasPainelView(CentralAnaliticaView):
    aba = "evidencias"


class AchadosPainelView(CentralAnaliticaView):
    aba = "achados"


class PreAnalisePainelView(CentralAnaliticaView):
    aba = "pre_analise"


class RevisaoPainelView(CentralAnaliticaView):
    aba = "revisao"


class IaTecnicoPainelView(CentralAnaliticaView):
    aba = "ia_tecnico"


class OperacaoPainelView(CentralAnaliticaView):
    aba = "operacao"


class FinOpsView(LoginRequiredMixin, TemplateView):
    template_name = "painel/finops.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtros = FiltrosPainel.da_requisicao(self.request.GET)
        contexto["filtros"] = filtros
        opcoes = opcoes_de_filtro("finops", filtros.origem)
        contexto["campos_filtro"] = descrever_campos("finops", filtros, opcoes)
        contexto["painel"] = montar_finops(filtros)
        return contexto


class ModuloIndisponivelView(LoginRequiredMixin, TemplateView):
    template_name = "painel/modulo_indisponivel.html"

    def get(self, request, *args, **kwargs):
        if kwargs.get("slug") == "finops":
            return redirect("painel:finops")
        return super().get(request, *args, **kwargs)

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

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["usuarios_total"] = Usuario.objects.count()
        contexto["usuarios_ativos"] = Usuario.objects.filter(is_active=True).count()
        contexto["por_perfil"] = list(Usuario.objects.values("perfil").annotate(quantidade=Count("id")).order_by("perfil"))
        contexto["eventos"] = list(RegistroAuditoria.objects.select_related("usuario").order_by("-data_hora")[:12])
        return contexto


class SaudeView(PerfilExigidoMixin, TemplateView):
    template_name = "painel/saude.html"
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["componentes"] = coletar_saude()
        contexto["verificado_em"] = timezone.localtime()
        return contexto


def viva(request):
    return JsonResponse({"aplicacao": "operacional"})
