from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.pareceres.escolhas import AcaoRevisaoPreAnalise, StatusParecerFinal
from aplicacao.pareceres.models import AfirmacaoPreAnalise, ParecerFinal, PreAnaliseTecnica
from aplicacao.pareceres.parecer_final import (
    aproveitar_sugestao,
    finalizar_parecer,
    obter_ou_criar_parecer,
    registrar_sugestao_ia,
    salvar_texto_analista,
)
from aplicacao.pareceres.revisao import ErroConcorrencia, ErroRevisaoPreAnalise, congelar, revisar_afirmacao
from aplicacao.pareceres.tarefas import gerar_pre_analise_task
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import (
    exigir_atuar_na_prestacao,
    exigir_ver_prestacao,
    pode_atuar_na_prestacao,
    pode_consultar,
    pode_executar_analise,
    pode_validar_analise,
    prestacoes_visiveis,
)


class ListaPreAnalisesView(LoginRequiredMixin, View):
    def get(self, request):
        if not pode_consultar(request.user):
            return redirect("painel:entrar")
        consulta = PreAnaliseTecnica.objects.select_related(
            "prestacao_contas",
            "solicitada_por",
            "modelo_inteligencia_artificial",
        ).filter(prestacao_contas__in=prestacoes_visiveis(request.user))
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
        pre = get_object_or_404(
            PreAnaliseTecnica.objects.select_related("prestacao_contas"),
            pk=pk,
        )
        exigir_ver_prestacao(request.user, pre.prestacao_contas)
        return render(request, "pareceres/detalhe.html", _contexto(request, pk))

    def post(self, request, pk):
        pre = get_object_or_404(PreAnaliseTecnica, pk=pk)
        exigir_ver_prestacao(request.user, pre.prestacao_contas)
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
                exigir_atuar_na_prestacao(request.user, pre.prestacao_contas)
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


class ParecerFinalView(LoginRequiredMixin, View):
    """Tela com sugestão IA, texto do analista e versão final — separados."""

    def get(self, request, prestacao_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_pk)
        exigir_ver_prestacao(request.user, prestacao)
        parecer = ParecerFinal.objects.filter(prestacao=prestacao).order_by("-versao").first()
        pode_atuar = pode_atuar_na_prestacao(request.user, prestacao)
        return render(
            request,
            "pareceres/parecer_final.html",
            {
                "prestacao": prestacao,
                "parecer": parecer,
                "pode_atuar": pode_atuar,
                "historico": list(parecer.historico.select_related("usuario")[:30]) if parecer else [],
                "versoes": list(ParecerFinal.objects.filter(prestacao=prestacao).order_by("-versao")[:20]),
            },
        )

    def post(self, request, prestacao_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_pk)
        exigir_atuar_na_prestacao(request.user, prestacao)
        acao = (request.POST.get("acao") or "").strip()
        parecer = obter_ou_criar_parecer(prestacao=prestacao, usuario=request.user)
        try:
            if acao == "registrar_sugestao":
                registrar_sugestao_ia(
                    parecer=parecer,
                    usuario=request.user,
                    texto=request.POST.get("sugestao_ia", ""),
                    request=request,
                )
                messages.success(request, "Sugestão de apoio registrada (não é decisão administrativa).")
            elif acao == "aproveitar_integral":
                aproveitar_sugestao(parecer=parecer, usuario=request.user, parcial=False, request=request)
                messages.success(request, "Sugestão copiada para o texto do analista. Revise antes de finalizar.")
            elif acao == "aproveitar_parcial":
                aproveitar_sugestao(parecer=parecer, usuario=request.user, parcial=True, request=request)
                messages.success(request, "Sugestão acrescentada ao texto do analista.")
            elif acao == "salvar_analista":
                salvar_texto_analista(
                    parecer=parecer,
                    usuario=request.user,
                    texto=request.POST.get("texto_analista", ""),
                    request=request,
                )
                messages.success(request, "Texto do analista salvo.")
            elif acao == "finalizar":
                finalizar_parecer(
                    parecer=parecer,
                    usuario=request.user,
                    texto_final=request.POST.get("texto_final"),
                    request=request,
                )
                messages.success(request, "Versão final consolidada pelo analista.")
            elif acao == "nova_versao":
                if parecer.status == StatusParecerFinal.FINALIZADO:
                    obter_ou_criar_parecer(prestacao=prestacao, usuario=request.user)
                    messages.success(request, "Nova versão de parecer aberta.")
                else:
                    messages.info(request, "Já existe versão em elaboração.")
            else:
                messages.error(request, "Ação não reconhecida.")
        except ValueError as erro:
            messages.error(request, str(erro))
        return redirect("pareceres:parecer_final", prestacao_pk=prestacao.pk)
