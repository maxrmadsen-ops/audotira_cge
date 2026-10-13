from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from aplicacao.diligencias.formularios import (
    FormularioEncerrarDiligencia,
    FormularioNovaDiligencia,
    FormularioRespostaDiligencia,
)
from aplicacao.diligencias.models import Diligencia
from aplicacao.diligencias.servico import abrir_diligencia, encerrar_diligencia, registrar_resposta_diligencia
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import (
    PerfilExigidoMixin,
    exigir_atuar_na_prestacao,
    exigir_ver_prestacao,
    pode_atuar_na_prestacao,
)
from aplicacao.usuarios.models import Usuario

PERFIS_OPERACIONAIS = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)


class NovaDiligenciaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, prestacao_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_pk)
        exigir_ver_prestacao(request.user, prestacao)
        exigir_atuar_na_prestacao(request.user, prestacao)
        return render(
            request,
            "diligencias/formulario.html",
            {
                "prestacao": prestacao,
                "form": FormularioNovaDiligencia(prestacao=prestacao),
                "titulo_pagina": "Nova diligência",
            },
        )

    def post(self, request, prestacao_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_pk)
        exigir_ver_prestacao(request.user, prestacao)
        exigir_atuar_na_prestacao(request.user, prestacao)
        form = FormularioNovaDiligencia(request.POST, prestacao=prestacao)
        if not form.is_valid():
            return render(
                request,
                "diligencias/formulario.html",
                {"prestacao": prestacao, "form": form, "titulo_pagina": "Nova diligência"},
            )
        diligencia = abrir_diligencia(
            prestacao=prestacao,
            usuario=request.user,
            motivo=form.cleaned_data["motivo"],
            descricao=form.cleaned_data["descricao"],
            prazo=form.cleaned_data.get("prazo"),
            documentos=form.cleaned_data.get("documentos"),
            request=request,
        )
        messages.success(request, f"Diligência {diligencia.identificador} aberta.")
        return redirect("diligencias:detalhe", pk=diligencia.pk)


class DetalheDiligenciaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, pk):
        diligencia = get_object_or_404(
            Diligencia.objects.select_related("prestacao", "solicitante", "encerrada_por").prefetch_related(
                "documentos", "historico__usuario"
            ),
            pk=pk,
        )
        exigir_ver_prestacao(request.user, diligencia.prestacao)
        pode_atuar = pode_atuar_na_prestacao(request.user, diligencia.prestacao)
        return render(
            request,
            "diligencias/detalhe.html",
            {
                "diligencia": diligencia,
                "prestacao": diligencia.prestacao,
                "pode_atuar": pode_atuar,
                "form_resposta": FormularioRespostaDiligencia() if pode_atuar else None,
                "form_encerrar": FormularioEncerrarDiligencia() if pode_atuar else None,
            },
        )


class RegistrarRespostaDiligenciaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, pk):
        diligencia = get_object_or_404(Diligencia.objects.select_related("prestacao"), pk=pk)
        exigir_atuar_na_prestacao(request.user, diligencia.prestacao)
        form = FormularioRespostaDiligencia(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe a resposta/manifestação recebida.")
            return redirect("diligencias:detalhe", pk=pk)
        try:
            registrar_resposta_diligencia(
                diligencia=diligencia,
                usuario=request.user,
                resposta=form.cleaned_data["resposta"],
                request=request,
            )
            messages.success(request, "Resposta registrada.")
        except ValueError as erro:
            messages.error(request, str(erro))
        return redirect("diligencias:detalhe", pk=pk)


class EncerrarDiligenciaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, pk):
        diligencia = get_object_or_404(Diligencia.objects.select_related("prestacao"), pk=pk)
        exigir_atuar_na_prestacao(request.user, diligencia.prestacao)
        form = FormularioEncerrarDiligencia(request.POST)
        observacao = form.cleaned_data.get("observacao", "") if form.is_valid() else ""
        encerrar_diligencia(
            diligencia=diligencia,
            usuario=request.user,
            observacao=observacao,
            request=request,
        )
        messages.success(request, f"Diligência {diligencia.identificador} encerrada.")
        return redirect("diligencias:detalhe", pk=pk)
