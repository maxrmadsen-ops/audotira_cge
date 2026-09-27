from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.pareceres.escolhas import AcaoRevisaoPreAnalise
from aplicacao.pareceres.models import AfirmacaoPreAnalise, PreAnaliseTecnica
from aplicacao.pareceres.revisao import ErroConcorrencia, ErroRevisaoPreAnalise, congelar, revisar_afirmacao
from aplicacao.pareceres.tarefas import gerar_pre_analise_task
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import pode_consultar, pode_executar_analise, pode_validar_analise


class ListaPreAnalisesView(LoginRequiredMixin, View):
    def get(self, request):
        if not pode_consultar(request.user):
            return redirect("painel:entrar")
        consulta = PreAnaliseTecnica.objects.select_related("prestacao_contas", "solicitada_por", "modelo_inteligencia_artificial")
        prestacao = request.GET.get("prestacao", "").strip()
        if prestacao:
            consulta = consulta.filter(prestacao_contas__numero_processo__icontains=prestacao)
        return render(
            request,
            "pareceres/lista.html",
            {"pre_analises": consulta[:200], "prestacao": prestacao, "pode_gerar": pode_executar_analise(request.user)},
        )


class DetalhePreAnaliseView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not pode_consultar(request.user):
            return redirect("painel:entrar")
        return render(request, "pareceres/detalhe.html", _contexto(request, pk))

    def post(self, request, pk):
        pre = get_object_or_404(PreAnaliseTecnica, pk=pk)
        acao = request.POST.get("acao", "")
        try:
            if acao == AcaoRevisaoPreAnalise.CONGELAR:
                if not pode_validar_analise(request.user):
                    return HttpResponseForbidden("Somente auditor ou administrador pode congelar a pré-análise.")
                congelar(pre, request.user)
                messages.success(request, "Pré-análise congelada.")
            elif acao in {AcaoRevisaoPreAnalise.ACEITAR, AcaoRevisaoPreAnalise.AJUSTAR, AcaoRevisaoPreAnalise.REJEITAR}:
                if not pode_executar_analise(request.user):
                    return HttpResponseForbidden("Perfil sem permissão para revisar a pré-análise.")
                afirmacao = get_object_or_404(AfirmacaoPreAnalise, pk=request.POST.get("afirmacao"), secao__pre_analise=pre)
                revisar_afirmacao(
                    pre,
                    afirmacao,
                    request.user,
                    acao,
                    texto=request.POST.get("texto", ""),
                    justificativa=request.POST.get("justificativa", ""),
                    versao_esperada=request.POST.get("versao_registro"),
                )
                messages.success(request, "Revisão registrada. O texto original da IA foi preservado.")
            else:
                messages.error(request, "Ação não permitida.")
        except ErroConcorrencia as erro:
            messages.error(request, str(erro))
        except ErroRevisaoPreAnalise as erro:
            messages.error(request, str(erro))
        return redirect("pareceres:detalhe", pk=pre.pk)


class GerarPreAnaliseView(LoginRequiredMixin, View):
    def post(self, request, prestacao_pk):
        if not pode_executar_analise(request.user):
            return HttpResponseForbidden("Perfil sem permissão para gerar a pré-análise.")
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_pk)
        analise = prestacao.execucoes_analise.order_by("-id").first()
        if analise is None:
            messages.error(request, "Não há execução de análise para esta prestação.")
            return redirect("prestacoes_contas:detalhe", pk=prestacao.pk)
        resultado = gerar_pre_analise_task.delay(analise.pk, request.user.pk)
        if resultado.ready():
            dados = resultado.get()
            if dados.get("id"):
                messages.success(request, f"Pré-análise {dados['codigo']} versão {dados['versao']} gerada.")
                return redirect("pareceres:detalhe", pk=dados["id"])
            messages.error(request, "A geração terminou com erro controlado. A versão com falha foi preservada.")
        else:
            messages.success(request, "Geração solicitada. A versão aparecerá quando o processamento terminar.")
        return redirect(f"/prestacoes/{prestacao.pk}/?aba=pre-analise")


class ExportarPreAnaliseView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not pode_consultar(request.user):
            return redirect("painel:entrar")
        pre = get_object_or_404(PreAnaliseTecnica.objects.select_related("prestacao_contas", "revisada_por", "congelada_por"), pk=pk)
        registrar_evento(
            evento=RegistroAuditoria.Evento.EXPORTACAO,
            descricao="Exportação HTML da pré-análise.",
            usuario=request.user,
            caminho=request.path,
            detalhes={"codigo": pre.codigo, "versao": pre.versao, "formato": "html"},
        )
        return render(request, "pareceres/exportar.html", _contexto(request, pk))


def contexto_aba(prestacao):
    versoes = prestacao.pre_analises.select_related("solicitada_por", "modelo_inteligencia_artificial").order_by("-versao")
    return {"pre_analises": versoes, "pre_analise_atual": versoes.first()}


def _contexto(request, pk):
    pre = get_object_or_404(
        PreAnaliseTecnica.objects.select_related(
            "prestacao_contas",
            "execucao_analise",
            "solicitada_por",
            "revisada_por",
            "congelada_por",
            "modelo_inteligencia_artificial",
            "versao_prompt",
        ).prefetch_related("secoes__afirmacoes__fontes__evidencia", "secoes__afirmacoes__fontes__achado", "secoes__afirmacoes__fontes__documento"),
        pk=pk,
    )
    return {
        "pre": pre,
        "versoes": pre.prestacao_contas.pre_analises.filter(execucao_analise=pre.execucao_analise).order_by("-versao"),
        "pode_revisar": pode_executar_analise(request.user) and not pre.congelada,
        "pode_congelar": pode_validar_analise(request.user) and not pre.congelada and pre.status != "erro",
        "pode_gerar": pode_executar_analise(request.user),
        "rejeitadas": AfirmacaoPreAnalise.objects.filter(secao__pre_analise=pre, exibir_oficial=False),
        "quantidade_afirmacoes": AfirmacaoPreAnalise.objects.filter(secao__pre_analise=pre, exibir_oficial=True).count(),
        "quantidade_limitacoes": AfirmacaoPreAnalise.objects.filter(secao__pre_analise=pre, secao__tipo="limitacoes", exibir_oficial=True).count(),
        "quantidade_achados": pre.execucao_analise.achados.count(),
        "quantidade_regras": pre.execucao_analise.execucoes.count(),
    }
