from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView, View

from aplicacao.entidades.models import Funcionario
from aplicacao.prestacoes_contas.auditoria_dominio import registrar_mutacao
from aplicacao.prestacoes_contas.formularios import (
    FormularioContrapartida,
    FormularioDespesa,
    FormularioDevolucao,
    FormularioDocumentoFiscal,
    FormularioFuncionario,
    FormularioItemPlano,
    FormularioMeta,
    FormularioMovimentacao,
    FormularioPagamento,
    FormularioParcial,
    FormularioPlano,
    FormularioPrestacao,
)
from aplicacao.prestacoes_contas.linha_do_tempo import montar_linha_do_tempo
from aplicacao.prestacoes_contas.models import PlanoTrabalho, PrestacaoContas
from aplicacao.usuarios.acesso import PerfilExigidoMixin, pode_executar_analise
from aplicacao.usuarios.models import Usuario

ABAS = (
    ("geral", "Visão Geral"),
    ("linha-do-tempo", "Linha do Tempo"),
    ("plano", "Plano de Trabalho"),
    ("financeiro", "Financeiro"),
    ("folha", "Folha de Pagamento"),
    ("documentos", "Documentos"),
    ("analise", "Análise"),
    ("achados", "Achados"),
    ("pre-analise", "Pré-Análise"),
)
ABAS_PREPARADAS = {"achados", "pre-analise"}
PERFIS_ALTERACAO = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)


class ListaPrestacoesView(LoginRequiredMixin, ListView):
    model = PrestacaoContas
    template_name = "prestacoes_contas/lista.html"
    context_object_name = "prestacoes"
    paginate_by = 20

    def get_queryset(self):
        consulta = PrestacaoContas.objects.select_related("concedente", "beneficiario")
        termo = self.request.GET.get("q", "").strip()
        situacao = self.request.GET.get("situacao", "").strip()
        fase = self.request.GET.get("fase", "").strip()
        if termo:
            consulta = consulta.filter(
                Q(numero_processo__icontains=termo)
                | Q(objeto__icontains=termo)
                | Q(concedente__nome__icontains=termo)
                | Q(beneficiario__nome__icontains=termo)
            )
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        if fase:
            consulta = consulta.filter(fase=fase)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["filtros"] = {
            "q": self.request.GET.get("q", ""),
            "situacao": self.request.GET.get("situacao", ""),
            "fase": self.request.GET.get("fase", ""),
        }
        contexto["situacoes"] = PrestacaoContas._meta.get_field("situacao").choices
        contexto["fases"] = PrestacaoContas._meta.get_field("fase").choices
        contexto["pode_alterar"] = pode_executar_analise(self.request.user)
        return contexto


class PrestacaoFormView(PerfilExigidoMixin):
    perfis_permitidos = PERFIS_ALTERACAO
    form_class = FormularioPrestacao
    template_name = "prestacoes_contas/formulario.html"

    def form_valid(self, form):
        nova = self.object.pk is None if getattr(self, "object", None) else True
        prestacao = form.save(commit=False)
        if nova:
            prestacao.criado_por = self.request.user
        prestacao.save()
        form._salvar_instrumento(prestacao)
        registrar_mutacao(
            usuario=self.request.user,
            acao="criacao" if nova else "alteracao",
            instancia=prestacao,
            campos=list(form.changed_data),
            request=self.request,
        )
        messages.success(self.request, "Prestação de contas registrada.")
        return redirect("prestacoes_contas:detalhe", pk=prestacao.pk)


class CriarPrestacaoView(PrestacaoFormView, CreateView):
    model = PrestacaoContas

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = "Nova prestação de contas"
        return contexto


class EditarPrestacaoView(PrestacaoFormView, UpdateView):
    model = PrestacaoContas

    def form_valid(self, form):
        self.object = self.get_object()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = f"Editar {self.object.numero_processo}"
        return contexto


class DetalhePrestacaoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from django.shortcuts import render

        prestacao = self._prestacao(pk)
        aba = request.GET.get("aba", "geral")
        if aba not in {codigo for codigo, _ in ABAS}:
            aba = "geral"
        return render(request, "prestacoes_contas/detalhe.html", self._contexto(request, prestacao, aba))

    def _prestacao(self, pk):
        return get_object_or_404(
            PrestacaoContas.objects.select_related("concedente", "beneficiario", "criado_por").prefetch_related(
                "instrumentos",
                "planos__itens",
                "planos__metas",
                "parciais",
                "despesas",
                "documentos_fiscais",
                "pagamentos",
                "movimentacoes",
                "contrapartidas",
                "devolucoes",
            ),
            pk=pk,
        )

    def _contexto(self, request, prestacao, aba):
        plano = prestacao.planos.first()
        contexto = {
            "prestacao": prestacao,
            "aba": aba,
            "abas": ABAS,
            "abas_preparadas": ABAS_PREPARADAS,
            "pode_alterar": pode_executar_analise(request.user),
            "linha_do_tempo": montar_linha_do_tempo(prestacao),
            "plano": plano,
            "funcionarios": Funcionario.objects.filter(entidade=prestacao.beneficiario).select_related("pessoa")
            if prestacao.beneficiario_id
            else Funcionario.objects.none(),
            "form_plano": FormularioPlano(),
            "form_item": FormularioItemPlano(plano=plano),
            "form_meta": FormularioMeta(),
            "form_parcial": FormularioParcial(),
            "form_despesa": FormularioDespesa(prestacao=prestacao),
            "form_documento": FormularioDocumentoFiscal(prestacao=prestacao),
            "form_pagamento": FormularioPagamento(prestacao=prestacao),
            "form_movimentacao": FormularioMovimentacao(prestacao=prestacao),
            "form_contrapartida": FormularioContrapartida(prestacao=prestacao),
            "form_devolucao": FormularioDevolucao(prestacao=prestacao),
            "form_funcionario": FormularioFuncionario(),
        }
        if aba == "documentos":
            from aplicacao.documentos.views import contexto_aba

            contexto.update(contexto_aba(request, prestacao))
        if aba == "analise":
            from aplicacao.regras.views import contexto_aba_analise

            contexto.update(contexto_aba_analise(request, prestacao))
        return contexto


class InclusaoNaPrestacaoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_ALTERACAO
    formulario = None
    aba = "geral"

    def post(self, request, pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        formulario = self.construir_formulario(request, prestacao)
        if formulario.is_valid():
            instancia = self.salvar(formulario, prestacao)
            registrar_mutacao(
                usuario=request.user,
                acao="criacao",
                instancia=instancia,
                campos=list(formulario.changed_data) if hasattr(formulario, "changed_data") else [],
                request=request,
            )
            messages.success(request, "Registro incluído.")
        else:
            messages.error(request, "Não foi possível incluir o registro. Revise os campos.")
        return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': prestacao.pk})}?aba={self.aba}")

    def construir_formulario(self, request, prestacao):
        return self.formulario(request.POST, prestacao=prestacao)

    def salvar(self, formulario, prestacao):
        instancia = formulario.save(commit=False)
        instancia.prestacao = prestacao
        instancia.demonstracao = prestacao.demonstracao
        instancia.save()
        if hasattr(formulario, "save_m2m"):
            formulario.save_m2m()
        return instancia


class IncluirPlanoView(InclusaoNaPrestacaoView):
    formulario = FormularioPlano
    aba = "plano"

    def construir_formulario(self, request, prestacao):
        return FormularioPlano(request.POST)

    def salvar(self, formulario, prestacao):
        plano = formulario.save(commit=False)
        plano.prestacao = prestacao
        plano.instrumento = prestacao.instrumento_principal
        plano.demonstracao = prestacao.demonstracao
        plano.save()
        return plano


class IncluirItemView(InclusaoNaPrestacaoView):
    aba = "plano"

    def post(self, request, pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        plano = prestacao.planos.order_by("versao").first()
        if plano is None:
            messages.error(request, "Inclua um plano de trabalho antes dos itens.")
            return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=plano")
        formulario = FormularioItemPlano(request.POST, plano=plano)
        if formulario.is_valid():
            item = formulario.save(commit=False)
            item.plano = plano
            item.demonstracao = prestacao.demonstracao
            item.save()
            registrar_mutacao(usuario=request.user, acao="criacao", instancia=item, campos=list(formulario.changed_data), request=request)
            messages.success(request, "Item previsto incluído.")
        else:
            messages.error(request, "Não foi possível incluir o item.")
        return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=plano")


class IncluirMetaView(InclusaoNaPrestacaoView):
    aba = "plano"

    def post(self, request, pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        plano = prestacao.planos.order_by("versao").first()
        if plano is None:
            messages.error(request, "Inclua um plano de trabalho antes das metas.")
            return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=plano")
        formulario = FormularioMeta(request.POST)
        if formulario.is_valid():
            meta = formulario.save(commit=False)
            meta.plano = plano
            meta.demonstracao = prestacao.demonstracao
            meta.save()
            registrar_mutacao(usuario=request.user, acao="criacao", instancia=meta, campos=list(formulario.changed_data), request=request)
            messages.success(request, "Meta incluída.")
        else:
            messages.error(request, "Não foi possível incluir a meta.")
        return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=plano")


class IncluirParcialView(InclusaoNaPrestacaoView):
    formulario = FormularioParcial
    aba = "linha-do-tempo"

    def construir_formulario(self, request, prestacao):
        return FormularioParcial(request.POST)


class IncluirDespesaView(InclusaoNaPrestacaoView):
    formulario = FormularioDespesa
    aba = "financeiro"


class IncluirDocumentoView(InclusaoNaPrestacaoView):
    formulario = FormularioDocumentoFiscal
    aba = "financeiro"

    def salvar(self, formulario, prestacao):
        documento = super().salvar(formulario, prestacao)
        despesa = formulario.cleaned_data.get("despesa")
        if despesa:
            documento.despesas.add(despesa)
        return documento


class IncluirPagamentoView(InclusaoNaPrestacaoView):
    formulario = FormularioPagamento
    aba = "financeiro"


class IncluirMovimentacaoView(InclusaoNaPrestacaoView):
    formulario = FormularioMovimentacao
    aba = "financeiro"


class IncluirContrapartidaView(InclusaoNaPrestacaoView):
    formulario = FormularioContrapartida
    aba = "financeiro"


class IncluirDevolucaoView(InclusaoNaPrestacaoView):
    formulario = FormularioDevolucao
    aba = "financeiro"


class IncluirFuncionarioView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_ALTERACAO

    def post(self, request, pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        if prestacao.beneficiario_id is None:
            messages.error(request, "Informe o beneficiário antes de registrar funcionários.")
            return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=folha")
        formulario = FormularioFuncionario(request.POST)
        if formulario.is_valid():
            funcionario = formulario.criar(prestacao.beneficiario, demonstracao=prestacao.demonstracao)
            registrar_mutacao(usuario=request.user, acao="criacao", instancia=funcionario, campos=["nome", "cargo"], request=request)
            messages.success(request, "Funcionário incluído.")
        else:
            messages.error(request, "Não foi possível incluir o funcionário.")
        return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=folha")
