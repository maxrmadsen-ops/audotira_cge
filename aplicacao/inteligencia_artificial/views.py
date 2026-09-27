from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.inteligencia_artificial.agentes import classe_do_agente
from aplicacao.inteligencia_artificial.gerenciador import GerenciadorInteligenciaArtificial, chave_idempotencia
from aplicacao.inteligencia_artificial.integracao import resumo_consumo
from aplicacao.inteligencia_artificial.models import (
    ConfiguracaoRoteamento,
    LimiteConsumoInteligenciaArtificial,
    ModeloInteligenciaArtificial,
    PrecoModeloInteligenciaArtificial,
    PromptInteligenciaArtificial,
    VersaoPromptInteligenciaArtificial,
)
from aplicacao.inteligencia_artificial.provedores.simulado import ProvedorInteligenciaArtificialSimulado
from aplicacao.inteligencia_artificial.sementes import garantir_catalogo_ia
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.regras.contexto import ContextoExecucao
from aplicacao.regras.models import ExecucaoRegra, RegraAnalise
from aplicacao.usuarios.acesso import PerfilExigidoMixin
from aplicacao.usuarios.models import Usuario

PERFIL_ADMIN = (Usuario.Perfil.ADMINISTRADOR,)


class ProvedoresView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_ADMIN

    def get(self, request):
        from django.conf import settings

        garantir_catalogo_ia()
        return render(
            request,
            "inteligencia_artificial/provedores.html",
            {
                "openai_habilitado": settings.OPENAI_HABILITADO,
                "anthropic_habilitado": settings.ANTHROPIC_HABILITADO,
                "integracao": settings.IA_INTEGRACAO,
                "openai_tem_chave": bool(settings.OPENAI_API_KEY),
                "anthropic_tem_chave": bool(settings.ANTHROPIC_API_KEY),
            },
        )


class CatalogoIaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_ADMIN
    template_name = "inteligencia_artificial/catalogo.html"

    def get(self, request):
        garantir_catalogo_ia()
        return render(
            request,
            self.template_name,
            {
                "modelos": ModeloInteligenciaArtificial.objects.all(),
                "prompts": PromptInteligenciaArtificial.objects.prefetch_related("versoes"),
                "precos": PrecoModeloInteligenciaArtificial.objects.select_related("modelo"),
                "limites": LimiteConsumoInteligenciaArtificial.objects.all(),
                "roteamento": ConfiguracaoRoteamento.objects.filter(ativo=True).select_related("modelo_principal", "modelo_fallback").first(),
            },
        )


class RoteamentoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_ADMIN

    def post(self, request):
        garantir_catalogo_ia()
        principal = get_object_or_404(ModeloInteligenciaArtificial, pk=request.POST.get("modelo_principal"))
        fallback = ModeloInteligenciaArtificial.objects.filter(pk=request.POST.get("modelo_fallback") or 0).first()
        configuracao = ConfiguracaoRoteamento.objects.filter(ativo=True).first()
        if configuracao is None:
            configuracao = ConfiguracaoRoteamento(nome="principal", ativo=True)
        configuracao.provedor_principal = principal.provedor
        configuracao.modelo_principal = principal
        configuracao.provedor_fallback = fallback.provedor if fallback else ""
        configuracao.modelo_fallback = fallback
        configuracao.save()
        messages.success(request, "Roteamento principal e fallback atualizados. Nenhuma chamada foi feita.")
        return redirect("ia:catalogo")


class ConsumoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_ADMIN

    def get(self, request):
        return render(request, "inteligencia_artificial/consumo.html", {"resumo": resumo_consumo()})


class LaboratorioView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_ADMIN

    def get(self, request):
        garantir_catalogo_ia()
        return render(request, "inteligencia_artificial/laboratorio.html", self._contexto())

    def post(self, request):
        garantir_catalogo_ia()
        prestacao = get_object_or_404(PrestacaoContas, pk=request.POST.get("prestacao"))
        regra = get_object_or_404(RegraAnalise, codigo=request.POST.get("regra"), ativa=True)
        modelo_a = get_object_or_404(ModeloInteligenciaArtificial, pk=request.POST.get("modelo_a"))
        modelo_b = get_object_or_404(ModeloInteligenciaArtificial, pk=request.POST.get("modelo_b"))
        antes = ExecucaoRegra.objects.count()
        contexto_execucao = ContextoExecucao.montar(prestacao, request.POST.get("teste_cego") == "1")
        comparacao = []
        for indice, modelo in enumerate((modelo_a, modelo_b), start=1):
            gerenciador = GerenciadorInteligenciaArtificial(
                ProvedorInteligenciaArtificialSimulado(),
                modelo_principal=modelo,
            )
            agente = classe_do_agente(regra.codigo)(gerenciador)
            chamada = agente.executar(
                regra,
                contexto_execucao,
                laboratorio=True,
                chave=chave_idempotencia("laboratorio", prestacao.pk, regra.codigo, modelo.pk, request.POST.get("chave") or indice),
            )
            comparacao.append({"modelo": modelo, "chamada": chamada})
        contexto = self._contexto()
        contexto.update(
            {
                "comparacao": comparacao,
                "regra_escolhida": regra,
                "prestacao_escolhida": prestacao,
                "oficial_inalterado": ExecucaoRegra.objects.count() == antes,
            }
        )
        return render(request, "inteligencia_artificial/laboratorio.html", contexto)

    def _contexto(self):
        return {
            "prestacoes": PrestacaoContas.objects.order_by("-id")[:30],
            "regras": RegraAnalise.objects.filter(ativa=True, capacidade="requer_ia").order_by("ordem"),
        "modelos": ModeloInteligenciaArtificial.objects.all(),
        }
