from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.regras.escolhas import (
    CapacidadeExecucao,
    Encaminhamento,
    REGRA_DE_OURO,
    StatusAnalise,
    StatusTecnico,
    TipoExecucaoTecnica,
)
from aplicacao.regras.models import ExecucaoAnalise, ExecucaoRegra, RegraAnalise
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
    "executada_ia": {"entradas__has_key": "ia"},
    "ia_inconclusiva": {"entradas__has_key": "ia", "resultado_funcional": "INCONCLUSIVO"},
    "erro_ia": {"entradas__ia__status": "erro_controlado"},
    "fallback": {"entradas__ia__fallback_utilizado": True},
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
        recente = (
            ExecucaoAnalise.objects.filter(
                prestacao_contas=prestacao,
                modo_teste_cego=modo_teste_cego,
                status=StatusAnalise.EM_ANDAMENTO,
                criado_em__gte=timezone.now() - timedelta(seconds=20),
            )
            .order_by("-criado_em")
            .first()
        )
        if recente is not None:
            messages.info(request, "Já existe uma análise em andamento para esta prestação.")
            return redirect("regras:progresso", pk=recente.pk)
        analise = criar_analise(prestacao=prestacao, usuario=request.user, modo_teste_cego=modo_teste_cego)
        executar_analise_task.delay(analise.pk)
        messages.success(request, "A análise foi registrada e permanece pendente de validação humana.")
        return redirect("regras:progresso", pk=analise.pk)


class ReexecutarRegraView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_EXECUCAO

    def post(self, request, pk, codigo):
        from django.conf import settings

        from aplicacao.inteligencia_artificial.agentes import classe_do_agente
        from aplicacao.inteligencia_artificial.integracao import vincular_usos
        from aplicacao.inteligencia_artificial.models import ModeloInteligenciaArtificial
        from aplicacao.inteligencia_artificial.provedores.simulado import ProvedorInteligenciaArtificialSimulado
        from aplicacao.inteligencia_artificial.gerenciador import GerenciadorInteligenciaArtificial
        from aplicacao.regras.contexto import ContextoExecucao

        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        execucao = (
            ExecucaoRegra.objects.filter(analise__prestacao_contas=prestacao, regra__codigo=codigo, regra__ativa=True)
            .select_related("regra", "analise")
            .order_by("-id")
            .first()
        )
        if execucao is None or execucao.regra.capacidade != CapacidadeExecucao.REQUER_IA:
            messages.error(request, "Não há execução semântica desta regra para reexecutar.")
            return redirect(f"/prestacoes/{prestacao.pk}/?aba=analise")
        if getattr(settings, "IA_INTEGRACAO", "desligada") == "desligada":
            messages.warning(request, "A integração de IA está desligada. A execução anterior foi preservada.")
            return redirect(f"/prestacoes/{prestacao.pk}/?aba=analise")
        historico = list(execucao.entradas.get("historico_ia") or [])
        if execucao.entradas.get("ia"):
            historico.append(execucao.entradas["ia"])
        tentativa = len(historico) + 1
        gerenciador = None
        if request.user.perfil == Usuario.Perfil.ADMINISTRADOR and request.POST.get("modelo"):
            modelo = get_object_or_404(ModeloInteligenciaArtificial, pk=request.POST.get("modelo"), ativo=True)
            gerenciador = GerenciadorInteligenciaArtificial(ProvedorInteligenciaArtificialSimulado(), modelo_principal=modelo)
        agente = classe_do_agente(execucao.regra.codigo)(gerenciador)
        contexto = ContextoExecucao.montar(prestacao, execucao.analise.modo_teste_cego)
        contexto.analise = execucao.analise
        chamada = agente.executar(execucao.regra, contexto, analise=execucao.analise, tentativa=tentativa)
        if chamada is None:
            messages.warning(request, "Não foi possível reexecutar. A execução anterior permanece.")
            return redirect(f"/prestacoes/{prestacao.pk}/?aba=analise")
        entradas = dict(execucao.entradas)
        entradas["historico_ia"] = historico
        entradas["ia"] = {
            "agente": agente.codigo,
            "provedor": chamada.provedor,
            "modelo": chamada.modelo,
            "versao_prompt": chamada.usos[-1].versao_prompt_id if chamada.usos else None,
            "resultado": chamada.resposta.get("resultado"),
            "justificativa": chamada.resposta.get("justificativa_resumida"),
            "fontes": chamada.resposta.get("fontes_utilizadas") or [],
            "fontes_rejeitadas": chamada.resposta.get("fontes_rejeitadas") or [],
            "fundamentos": chamada.resposta.get("fundamentos_normativos") or [],
            "limitacoes": chamada.resposta.get("limitacoes") or [],
            "revisao_humana": True,
            "tokens_entrada": sum(uso.tokens_entrada for uso in chamada.usos),
            "tokens_saida": sum(uso.tokens_saida for uso in chamada.usos),
            "latencia_ms": sum(uso.duracao_ms for uso in chamada.usos),
            "custo_estimado_total": "",
            "fallback_utilizado": chamada.fallback_utilizado,
            "status": chamada.status,
            "tentativa": tentativa,
        }
        entradas["usos"] = list(entradas.get("usos") or []) + [uso.pk for uso in chamada.usos]
        entradas["resultado_pre_ia"] = execucao.resultado_funcional
        execucao.entradas = entradas
        execucao.resultado_funcional = (chamada.resposta.get("resultado") or "INCONCLUSIVO")[:120]
        execucao.limitacao = " ".join(entradas["ia"]["limitacoes"])[:1000]
        execucao.encaminhamento = Encaminhamento.REQUER_IA
        execucao.save()
        vincular_usos(execucao, [uso.pk for uso in chamada.usos])
        messages.success(request, "Nova tentativa registrada. A execução anterior permanece no histórico e a revisão humana continua obrigatória.")
        return redirect(f"/prestacoes/{prestacao.pk}/?aba=analise")


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
    administrador = getattr(request.user, "perfil", "") == Usuario.Perfil.ADMINISTRADOR
    modelos = []
    if administrador:
        from aplicacao.inteligencia_artificial.models import ModeloInteligenciaArtificial

        modelos = list(ModeloInteligenciaArtificial.objects.filter(ativo=True))
    return {
        "analise": analise,
        "grupos_analise": grupos,
        "filtro_analise": filtro,
        "pode_executar": pode_executar_analise(request.user),
        "pode_escolher_modelo": administrador,
        "modelos_ia": modelos,
        "regra_de_ouro": REGRA_DE_OURO,
        "historico_analises": prestacao.execucoes_analise.order_by("-criado_em")[:8],
    }
