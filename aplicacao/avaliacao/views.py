from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.avaliacao.escolhas import CRITICAS, ClassificacaoCorrespondencia, ModoGroundTruth, StatusAvaliacao
from aplicacao.avaliacao.excecoes import ErroAvaliacao, ErroConcorrencia
from aplicacao.avaliacao.executar import criar_avaliacao, criticos
from aplicacao.avaliacao.ground_truth import (
    adicionar_achado,
    congelar,
    criar_ground_truth,
    definir_regra,
    enviar_validacao,
    validar,
)
from aplicacao.avaliacao.metricas import texto_metrica
from aplicacao.avaliacao.models import (
    AvaliacaoInteligenciaArtificial,
    CorrespondenciaAchado,
    GroundTruthPrestacao,
)
from aplicacao.avaliacao.permissoes import (
    pode_colaborar_ground_truth,
    pode_concluir_avaliacao,
    pode_congelar_ground_truth,
    pode_ler_avaliacao,
    pode_revisar_correspondencia,
    pode_validar_ground_truth,
)
from aplicacao.avaliacao.revisao import revisar_correspondencia
from aplicacao.avaliacao.tarefas import executar_avaliacao_task
from aplicacao.normas.models import Norma
from aplicacao.pareceres.escolhas import StatusPreAnalise
from aplicacao.pareceres.models import PreAnaliseTecnica
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.regras.models import RegraAnalise
from decimal import Decimal, InvalidOperation

ABAS = (
    ("resumo", "Resumo"),
    ("regras", "Regras"),
    ("achados", "Achados"),
    ("falsos-positivos", "Falsos Positivos"),
    ("falsos-negativos", "Falsos Negativos"),
    ("correspondencias", "Correspondências"),
    ("pre-analise", "Pré-Análise"),
    ("proveniencia", "Proveniência"),
    ("modelos", "Modelos"),
    ("auditoria", "Auditoria"),
)


def _negar():
    return HttpResponseForbidden("Perfil sem permissão para esta ação.")


def contexto_construcao(ground_truth) -> dict:
    prestacao = ground_truth.prestacao_contas
    contexto = {
        "modo": ground_truth.modo,
        "documentos": [{"id": item.pk, "nome": item.nome_original} for item in prestacao.documentos.all()],
        "normas": [{"id": item.pk, "titulo": item.titulo} for item in Norma.objects.filter(situacao="vigente").order_by("titulo")[:30]],
    }
    if ground_truth.modo == ModoGroundTruth.CEGO:
        return contexto
    contexto["achados"] = [{"codigo": item.codigo, "titulo": item.titulo} for item in prestacao.achados.all()]
    contexto["pre_analises"] = [
        {"codigo": item.codigo, "encaminhamento": item.encaminhamento, "resumo": item.resumo_executivo}
        for item in prestacao.pre_analises.all()
    ]
    return contexto


class ListaAvaliacaoView(LoginRequiredMixin, View):
    def get(self, request):
        if not pode_ler_avaliacao(request.user):
            return _negar()
        return render(
            request,
            "avaliacao/lista.html",
            {
                "ground_truths": GroundTruthPrestacao.objects.select_related("prestacao_contas"),
                "avaliacoes": AvaliacaoInteligenciaArtificial.objects.select_related("prestacao_contas", "ground_truth"),
                "pode_colaborar": pode_colaborar_ground_truth(request.user),
            },
        )


class CriarGroundTruthView(LoginRequiredMixin, View):
    def post(self, request):
        if not pode_colaborar_ground_truth(request.user):
            return _negar()
        prestacao = get_object_or_404(PrestacaoContas, pk=request.POST.get("prestacao"))
        modo = request.POST.get("modo") or ModoGroundTruth.CEGO
        if modo not in ModoGroundTruth.values:
            messages.error(request, "Modo de Ground Truth inválido.")
            return redirect("avaliacao:lista")
        ground_truth = criar_ground_truth(prestacao, request.user, modo, request.POST.get("observacoes", ""))
        messages.success(request, f"Ground Truth {ground_truth.codigo} criado em modo {ground_truth.get_modo_display()}.")
        return redirect("avaliacao:ground_truth", pk=ground_truth.pk)


class DetalheGroundTruthView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not pode_ler_avaliacao(request.user):
            return _negar()
        ground_truth = get_object_or_404(
            GroundTruthPrestacao.objects.select_related("prestacao_contas").prefetch_related("regras_referencia__regra", "achados_referencia"),
            pk=pk,
        )
        return render(
            request,
            "avaliacao/ground_truth.html",
            {
                "ground_truth": ground_truth,
                "contexto": contexto_construcao(ground_truth),
                "regras": RegraAnalise.objects.filter(ativa=True).order_by("codigo")[:100],
                "versoes": GroundTruthPrestacao.objects.filter(codigo=ground_truth.codigo).order_by("versao"),
                "pode_colaborar": pode_colaborar_ground_truth(request.user),
                "pode_validar": pode_validar_ground_truth(request.user),
                "pode_congelar": pode_congelar_ground_truth(request.user),
            },
        )


class ContextoGroundTruthView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not pode_ler_avaliacao(request.user):
            return _negar()
        ground_truth = get_object_or_404(GroundTruthPrestacao.objects.select_related("prestacao_contas"), pk=pk)
        return JsonResponse(contexto_construcao(ground_truth))


class RegraGroundTruthView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ground_truth = get_object_or_404(GroundTruthPrestacao, pk=pk)
        regra = get_object_or_404(RegraAnalise, pk=request.POST.get("regra"))
        try:
            definir_regra(
                ground_truth,
                request.user,
                regra,
                request.POST.get("resultado_esperado", ""),
                aplicavel=request.POST.get("aplicavel") == "1",
                justificativa=request.POST.get("justificativa", ""),
                versao_esperada=request.POST.get("versao_registro"),
            )
        except (ErroAvaliacao, ErroConcorrencia) as erro:
            messages.error(request, str(erro))
        return redirect("avaliacao:ground_truth", pk=pk)


class AchadoGroundTruthView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ground_truth = get_object_or_404(GroundTruthPrestacao, pk=pk)
        materialidade = None
        bruto = (request.POST.get("materialidade") or "").strip()
        if bruto:
            try:
                materialidade = Decimal(bruto.replace(",", "."))
            except InvalidOperation:
                messages.error(request, "Materialidade inválida.")
                return redirect("avaliacao:ground_truth", pk=pk)
        try:
            adicionar_achado(
                ground_truth,
                request.user,
                titulo=request.POST.get("titulo", ""),
                descricao=request.POST.get("descricao", ""),
                fato=request.POST.get("fato", ""),
                categoria=request.POST.get("categoria", ""),
                materialidade=materialidade,
                criticidade=request.POST.get("criticidade") or "baixa",
                versao_esperada=request.POST.get("versao_registro"),
            )
        except (ErroAvaliacao, ErroConcorrencia) as erro:
            messages.error(request, str(erro))
        return redirect("avaliacao:ground_truth", pk=pk)


class _TransicaoGroundTruthView(LoginRequiredMixin, View):
    acao = None

    def post(self, request, pk):
        ground_truth = get_object_or_404(GroundTruthPrestacao, pk=pk)
        try:
            self.acao(ground_truth, request.user, versao_esperada=request.POST.get("versao_registro"))
        except ErroAvaliacao as erro:
            texto = str(erro)
            if "permissão" in texto.casefold() or "somente o auditor" in texto.casefold() or "autoridade técnica" in texto.casefold():
                return HttpResponseForbidden(texto)
            messages.error(request, texto)
            return redirect("avaliacao:ground_truth", pk=pk)
        return redirect("avaliacao:ground_truth", pk=pk)


class EnviarGroundTruthView(_TransicaoGroundTruthView):
    acao = staticmethod(enviar_validacao)


class ValidarGroundTruthView(_TransicaoGroundTruthView):
    acao = staticmethod(validar)


class CongelarGroundTruthView(_TransicaoGroundTruthView):
    acao = staticmethod(congelar)


class IniciarAvaliacaoView(LoginRequiredMixin, View):
    def post(self, request):
        pre = get_object_or_404(PreAnaliseTecnica, pk=request.POST.get("pre_analise"))
        ground_truth = get_object_or_404(GroundTruthPrestacao, pk=request.POST.get("ground_truth"))
        try:
            avaliacao = criar_avaliacao(pre, ground_truth, request.user)
            executar_avaliacao_task(avaliacao.pk, request.user.pk)
            avaliacao.refresh_from_db()
        except ErroAvaliacao as erro:
            texto = str(erro)
            if "permissão" in texto.casefold() or "somente o auditor" in texto.casefold():
                return HttpResponseForbidden(texto)
            messages.error(request, texto)
            return redirect("avaliacao:lista")
        messages.success(request, f"Avaliação {avaliacao.codigo} em {avaliacao.get_status_display()}.")
        return redirect("avaliacao:detalhe", pk=avaliacao.pk)


class DetalheAvaliacaoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not pode_ler_avaliacao(request.user):
            return _negar()
        avaliacao = get_object_or_404(
            AvaliacaoInteligenciaArtificial.objects.select_related(
                "prestacao_contas", "ground_truth", "snapshot", "snapshot__pre_analise", "iniciado_por"
            ),
            pk=pk,
        )
        aba = request.GET.get("aba", "resumo")
        if aba not in {codigo for codigo, _ in ABAS}:
            aba = "resumo"
        correspondencias = list(
            avaliacao.correspondencias.select_related("achado", "ground_truth_achado").prefetch_related(
                "ground_truth_achado__regras",
                "ground_truth_achado__evidencias",
                "ground_truth_achado__normas",
                "ground_truth_achado__trechos",
            )
        )
        metricas = avaliacao.metricas or {}
        return render(
            request,
            "avaliacao/detalhe.html",
            {
                "avaliacao": avaliacao,
                "aba": aba,
                "abas": ABAS,
                "correspondencias": correspondencias,
                "comparacoes": avaliacao.comparacoes_regra.select_related("regra"),
                "criticos": criticos(correspondencias),
                "metricas": metricas,
                "precisao": texto_metrica(_decimal(metricas.get("precisao"))),
                "recall": texto_metrica(_decimal(metricas.get("recall"))),
                "f1": texto_metrica(_decimal(metricas.get("f1"))),
                "concordancia": texto_metrica(_decimal((metricas.get("regras") or {}).get("totais", {}).get("concordancia"))),
                "pode_revisar": pode_revisar_correspondencia(request.user),
                "pode_concluir": pode_concluir_avaliacao(request.user),
                "classificacoes": ClassificacaoCorrespondencia,
                "auditoria": _auditoria(avaliacao),
            },
        )


class RevisarCorrespondenciaView(LoginRequiredMixin, View):
    def post(self, request, pk, correspondencia_pk):
        correspondencia = get_object_or_404(CorrespondenciaAchado, pk=correspondencia_pk, avaliacao_id=pk)
        try:
            revisar_correspondencia(
                correspondencia,
                request.user,
                request.POST.get("acao", ""),
                classificacao=request.POST.get("classificacao", ""),
                justificativa=request.POST.get("justificativa", ""),
                observacao=request.POST.get("observacao", ""),
                versao_esperada=request.POST.get("versao_registro"),
            )
        except (ErroAvaliacao, ErroConcorrencia) as erro:
            texto = str(erro)
            if "permissão" in texto.casefold() or "somente o auditor" in texto.casefold():
                return HttpResponseForbidden(texto)
            messages.error(request, texto)
        return redirect("avaliacao:detalhe", pk=pk)


class ConcluirAvaliacaoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        avaliacao = get_object_or_404(AvaliacaoInteligenciaArtificial, pk=pk)
        try:
            from aplicacao.avaliacao.executar import concluir

            concluir(avaliacao, request.user)
        except ErroAvaliacao as erro:
            texto = str(erro)
            if "permissão" in texto.casefold() or "somente o auditor" in texto.casefold():
                return HttpResponseForbidden(texto)
            messages.error(request, texto)
        return redirect("avaliacao:detalhe", pk=pk)


class CongelarAvaliacaoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        avaliacao = get_object_or_404(AvaliacaoInteligenciaArtificial, pk=pk)
        try:
            from aplicacao.avaliacao.executar import congelar_avaliacao

            congelar_avaliacao(avaliacao, request.user)
        except ErroAvaliacao as erro:
            texto = str(erro)
            if "permissão" in texto.casefold() or "somente o auditor" in texto.casefold() or "autoridade técnica" in texto.casefold():
                return HttpResponseForbidden(texto)
            messages.error(request, texto)
        return redirect("avaliacao:detalhe", pk=pk)


class FalsoNegativoView(LoginRequiredMixin, View):
    def get(self, request, pk, correspondencia_pk):
        if not pode_ler_avaliacao(request.user):
            return _negar()
        correspondencia = get_object_or_404(
            CorrespondenciaAchado.objects.select_related("avaliacao", "avaliacao__snapshot__pre_analise", "ground_truth_achado"),
            pk=correspondencia_pk,
            avaliacao_id=pk,
            classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO,
        )
        referencia = correspondencia.ground_truth_achado
        return render(
            request,
            "avaliacao/falso_negativo.html",
            {
                "correspondencia": correspondencia,
                "referencia": referencia,
                "regras": referencia.regras.all() if referencia else [],
                "evidencias": referencia.evidencias.select_related("documento") if referencia else [],
                "normas": referencia.normas.all() if referencia else [],
                "trechos": referencia.trechos.all() if referencia else [],
                "critico": bool(referencia and referencia.criticidade in CRITICAS),
                "pre_analise": correspondencia.avaliacao.snapshot.pre_analise if correspondencia.avaliacao.snapshot_id else None,
            },
        )


def contexto_aba(request, prestacao):
    return {
        "ground_truths": prestacao.ground_truths.all(),
        "avaliacoes_ia": prestacao.avaliacoes_ia.select_related("ground_truth"),
        "pre_analises_congeladas": prestacao.pre_analises.filter(status=StatusPreAnalise.CONGELADA),
        "pode_colaborar_gt": pode_colaborar_ground_truth(request.user),
        "pode_iniciar_avaliacao": pode_concluir_avaliacao(request.user),
        "modos_ground_truth": ModoGroundTruth.choices,
    }


def _decimal(valor):
    if valor in (None, ""):
        return None
    return Decimal(str(valor))


def _auditoria(avaliacao):
    from aplicacao.auditoria.models import RegistroAuditoria

    return RegistroAuditoria.objects.filter(detalhes__codigo=avaliacao.codigo).order_by("-data_hora")[:30]
