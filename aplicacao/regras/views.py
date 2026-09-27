from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.regras.escolhas import CapacidadeExecucao, Encaminhamento, REGRA_DE_OURO, StatusTecnico, TipoExecucaoTecnica
from aplicacao.regras.models import ExecucaoAnalise, RegraAnalise
from aplicacao.regras.motor import criar_analise
from aplicacao.regras.tarefas import executar_analise_task
from aplicacao.usuarios.acesso import PerfilExigidoMixin, pode_executar_analise
from aplicacao.usuarios.models import Usuario

PERFIS_LEITURA = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
    Usuario.Perfil.CONSULTA,
)
PERFIS_EXECUCAO = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)

FILTROS_ANALISE = {
    "divergencia": {"status_tecnico": StatusTecnico.DIVERGENCIA},
    "atencao": {"status_tecnico": StatusTecnico.ATENCAO},
    "nao_verificavel": {"resultado_funcional": "NÃO VERIFICÁVEL"},
    "requer_ia": {"encaminhamento": Encaminhamento.REQUER_IA},
    "requer_analista": {"encaminhamento": Encaminhamento.REQUER_ANALISTA},
    "nao_aplicavel": {"status_tecnico": StatusTecnico.NAO_APLICAVEL},
    "erro": {"status_tecnico": StatusTecnico.ERRO},
}


class ListaRegrasView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_LEITURA

    def get(self, request):
        regras = RegraAnalise.objects.all()
        if request.GET.get("ativa", "1") != "todas":
            regras = regras.filter(ativa=True)
        categoria = request.GET.get("categoria", "")
        tipo = request.GET.get("tipo", "")
        capacidade = request.GET.get("capacidade", "")
        resultado = request.GET.get("resultado", "").strip()
        if categoria:
            regras = regras.filter(categoria=categoria)
        if tipo:
            regras = regras.filter(tipo_execucao=tipo)
        if capacidade:
            regras = regras.filter(capacidade=capacidade)
        if resultado:
            regras = regras.filter(resultados_possiveis__icontains=resultado)
        categorias = []
        for categoria_item in RegraAnalise.objects.filter(ativa=True).order_by("ordem").values_list("categoria", flat=True):
            if categoria_item not in categorias:
                categorias.append(categoria_item)
        return render(
            request,
            "regras/lista.html",
            {
                "regras": regras.order_by("ordem", "codigo"),
                "categorias": categorias,
                "tipos": TipoExecucaoTecnica.choices,
                "capacidades": CapacidadeExecucao.choices,
                "filtros": {
                    "categoria": categoria,
                    "tipo": tipo,
                    "capacidade": capacidade,
                    "ativa": request.GET.get("ativa", "1"),
                    "resultado": resultado,
                },
                "regra_de_ouro": REGRA_DE_OURO,
            },
        )


class DetalheRegraView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_LEITURA

    def get(self, request, codigo):
        regras = RegraAnalise.objects.filter(codigo=codigo).prefetch_related("dependencias").order_by("-versao")
        regra = regras.filter(ativa=True).first() or regras.first()
        if regra is None:
            from django.http import Http404

            raise Http404("Regra não encontrada.")
        return render(
            request,
            "regras/detalhe.html",
            {"regra": regra, "historico": regras, "regra_de_ouro": REGRA_DE_OURO},
        )


class ExecutarAnaliseView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_EXECUCAO

    def post(self, request, pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        modo_teste_cego = request.POST.get("modo") == "teste_cego"
        analise = criar_analise(prestacao=prestacao, usuario=request.user, modo_teste_cego=modo_teste_cego)
        executar_analise_task.delay(analise.pk)
        messages.success(request, "A análise foi registrada e permanece pendente de validação humana.")
        return redirect("regras:progresso", pk=analise.pk)


class ProgressoAnaliseView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_LEITURA

    def get(self, request, pk):
        analise = get_object_or_404(ExecucaoAnalise.objects.select_related("prestacao_contas"), pk=pk)
        return render(request, "regras/progresso.html", {"analise": analise, "regra_de_ouro": REGRA_DE_OURO})


def contexto_aba_analise(request, prestacao):
    analise = prestacao.execucoes_analise.order_by("-criado_em").first()
    filtro = request.GET.get("filtro", "")
    grupos = []
    if analise is not None:
        consulta = analise.execucoes.select_related("regra").prefetch_related("referencias", "calculos")
        criterio = FILTROS_ANALISE.get(filtro)
        if criterio:
            consulta = consulta.filter(**criterio)
        categoria = None
        for execucao in consulta.order_by("ordem", "id"):
            if execucao.regra.categoria != categoria:
                categoria = execucao.regra.categoria
                grupos.append({"categoria": categoria, "itens": []})
            grupos[-1]["itens"].append(execucao)
    return {
        "analise": analise,
        "grupos_analise": grupos,
        "filtro_analise": filtro,
        "pode_executar": pode_executar_analise(request.user),
        "regra_de_ouro": REGRA_DE_OURO,
        "historico_analises": prestacao.execucoes_analise.order_by("-criado_em")[:8],
    }
