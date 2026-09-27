from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.achados.escolhas import AcaoRevisao, Criticidade, NaturezaAchado, OrigemGeracao, PapelEvidencia, Prioridade, StatusAchado, TipoConstatacao
from aplicacao.achados.metricas import da_prestacao, indicadores_gerais
from aplicacao.achados.models import Achado
from aplicacao.achados.revisao import ErroRevisao, registrar_evidencia_humana, revisar
from aplicacao.usuarios.acesso import pode_consultar


class ListaAchadosView(LoginRequiredMixin, View):
    def get(self, request):
        if not pode_consultar(request.user):
            return redirect("painel:entrar")
        consulta = Achado.objects.select_related("prestacao_contas")
        filtros = {
            "prestacao": request.GET.get("prestacao", "").strip(),
            "categoria": request.GET.get("categoria", "").strip(),
            "natureza": request.GET.get("natureza", "").strip(),
            "criticidade": request.GET.get("criticidade", "").strip(),
            "prioridade": request.GET.get("prioridade", "").strip(),
            "status": request.GET.get("status", "").strip(),
            "regra": request.GET.get("regra", "").strip(),
            "materialidade": request.GET.get("materialidade", "").strip(),
            "origem": request.GET.get("origem", "").strip(),
            "revisao": request.GET.get("revisao", "").strip(),
        }
        if filtros["prestacao"]:
            consulta = consulta.filter(prestacao_contas__numero_processo__icontains=filtros["prestacao"])
        if filtros["categoria"]:
            consulta = consulta.filter(categoria=filtros["categoria"])
        if filtros["natureza"]:
            consulta = consulta.filter(natureza=filtros["natureza"])
        if filtros["criticidade"]:
            consulta = consulta.filter(criticidade=filtros["criticidade"])
        if filtros["prioridade"]:
            consulta = consulta.filter(prioridade=filtros["prioridade"])
        if filtros["status"]:
            consulta = consulta.filter(status=filtros["status"])
        if filtros["regra"]:
            consulta = consulta.filter(vinculos_regra__regra__codigo__iexact=filtros["regra"]).distinct()
        if filtros["materialidade"] == "com":
            consulta = consulta.filter(materialidade_financeira__isnull=False)
        elif filtros["materialidade"] == "sem":
            consulta = consulta.filter(materialidade_financeira__isnull=True)
        if filtros["origem"]:
            consulta = consulta.filter(origem_geracao=filtros["origem"])
        if filtros["revisao"] == "com":
            consulta = consulta.filter(revisoes__isnull=False).distinct()
        elif filtros["revisao"] == "sem":
            consulta = consulta.filter(revisoes__isnull=True)
        return render(
            request,
            "achados/lista.html",
            {
                "achados": consulta[:200],
                "indicadores": indicadores_gerais(),
                "filtros": filtros,
                "naturezas": NaturezaAchado.choices,
                "criticidades": Criticidade.choices,
                "prioridades": Prioridade.choices,
                "status_opcoes": StatusAchado.choices,
                "origens": OrigemGeracao.choices,
            },
        )


class DetalheAchadoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        achado = self._achado(pk)
        return render(request, "achados/detalhe.html", self._contexto(achado))

    def post(self, request, pk):
        achado = self._achado(pk)
        acao = request.POST.get("acao", "")
        try:
            if acao == "evidencia_humana":
                registrar_evidencia_humana(
                    achado,
                    request.user,
                    request.POST.get("trecho", ""),
                    request.POST.get("papel") or PapelEvidencia.SUPORTA,
                )
                messages.success(request, "Evidência humana registrada. Ela não substitui a evidência automática.")
            elif acao in AcaoRevisao.values:
                revisar(
                    achado,
                    request.user,
                    acao,
                    justificativa=request.POST.get("justificativa", ""),
                    comentario=request.POST.get("comentario", ""),
                    campos={
                        chave: request.POST.get(chave)
                        for chave in ("titulo", "descricao_factual", "interpretacao", "possivel_implicacao", "criticidade", "prioridade")
                        if request.POST.get(chave)
                    },
                )
                messages.success(request, "Revisão registrada. A saída original do sistema foi preservada.")
            else:
                messages.error(request, "Ação não reconhecida.")
        except ErroRevisao as erro:
            messages.error(request, str(erro))
        return redirect("achados:detalhe", pk=achado.pk)

    def _achado(self, pk):
        return get_object_or_404(
            Achado.objects.select_related("prestacao_contas", "analise").prefetch_related(
                "vinculos_regra__regra",
                "vinculos_regra__execucao",
                "vinculos_evidencia__evidencia__documento",
                "vinculos_evidencia__evidencia__pagina_documento",
                "fundamentacoes__norma",
                "fundamentacoes__trecho_normativo",
                "revisoes__usuario",
                "sinalizacoes",
            ),
            pk=pk,
        )

    def _contexto(self, achado):
        evidencia_documento = next(
            (
                vinculo.evidencia
                for vinculo in achado.vinculos_evidencia.all()
                if vinculo.evidencia.documento_id and vinculo.evidencia.pagina_documento_id
            ),
            None,
        )
        return {
            "achado": achado,
            "evidencia_documento": evidencia_documento,
            "acoes": AcaoRevisao.choices,
            "papeis": PapelEvidencia.choices,
            "criticidades": Criticidade.choices,
            "prioridades": Prioridade.choices,
            "tipos": TipoConstatacao.choices,
        }


def contexto_aba(prestacao):
    return da_prestacao(prestacao)
