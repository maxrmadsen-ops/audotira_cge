"""Gestão de usuários restrita ao Administrador."""

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.usuarios.acesso import PerfilExigidoMixin, pode_gerenciar_usuarios
from aplicacao.usuarios.models import Usuario


class FormularioUsuarioAdmin(forms.ModelForm):
    senha = forms.CharField(
        label="Senha inicial",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Obrigatória na criação. Em edição, deixe em branco para manter a senha.",
    )

    class Meta:
        model = Usuario
        fields = ("username", "first_name", "last_name", "email", "perfil", "is_active")

    def __init__(self, *args, **kwargs):
        self.criacao = kwargs.pop("criacao", False)
        super().__init__(*args, **kwargs)
        escolhas = [
            (Usuario.Perfil.ADMINISTRADOR, "Administrador"),
            (Usuario.Perfil.AUDITOR, "Auditor"),
            (Usuario.Perfil.ANALISTA, "Analista"),
        ]
        # Usuário legado CONSULTA: exibe o valor atual só para permitir migração para perfil operacional.
        atual = getattr(self.instance, "perfil", None)
        if atual == Usuario.Perfil.CONSULTA:
            escolhas = [(Usuario.Perfil.CONSULTA, "Consulta (legado — migrar)")] + escolhas
        self.fields["perfil"].choices = escolhas
        if self.criacao:
            self.fields["senha"].required = True

    def clean_perfil(self):
        perfil = self.cleaned_data["perfil"]
        if self.criacao and perfil == Usuario.Perfil.CONSULTA:
            raise forms.ValidationError("Não é permitido atribuir o perfil legado Consulta a novos usuários.")
        if perfil not in {
            Usuario.Perfil.ADMINISTRADOR,
            Usuario.Perfil.AUDITOR,
            Usuario.Perfil.ANALISTA,
            Usuario.Perfil.CONSULTA,
        }:
            raise forms.ValidationError("Perfil inválido.")
        if perfil == Usuario.Perfil.CONSULTA and not self.criacao:
            # Mantém apenas se já era CONSULTA; novos salvamentos devem migrar.
            if getattr(self.instance, "perfil", None) != Usuario.Perfil.CONSULTA:
                raise forms.ValidationError("Perfil operacional inválido.")
        return perfil


class ListaUsuariosView(PerfilExigidoMixin, View):
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)

    def get(self, request):
        usuarios = Usuario.objects.order_by("username")
        return render(
            request,
            "usuarios/lista.html",
            {"usuarios": usuarios, "pode_gerenciar": pode_gerenciar_usuarios(request.user)},
        )


class FormularioUsuarioView(PerfilExigidoMixin, View):
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)

    def get(self, request, pk=None):
        usuario = get_object_or_404(Usuario, pk=pk) if pk else None
        form = FormularioUsuarioAdmin(instance=usuario, criacao=usuario is None)
        return render(
            request,
            "usuarios/formulario.html",
            {
                "form": form,
                "usuario_alvo": usuario,
                "titulo_pagina": "Editar usuário" if usuario else "Novo usuário",
            },
        )

    def post(self, request, pk=None):
        usuario = get_object_or_404(Usuario, pk=pk) if pk else None
        criacao = usuario is None
        perfil_anterior = usuario.perfil if usuario else ""
        form = FormularioUsuarioAdmin(request.POST, instance=usuario, criacao=criacao)
        if not form.is_valid():
            return render(
                request,
                "usuarios/formulario.html",
                {
                    "form": form,
                    "usuario_alvo": usuario,
                    "titulo_pagina": "Editar usuário" if usuario else "Novo usuário",
                },
            )
        alvo = form.save(commit=False)
        alvo.is_staff = alvo.perfil == Usuario.Perfil.ADMINISTRADOR
        alvo.is_superuser = alvo.perfil == Usuario.Perfil.ADMINISTRADOR
        senha = form.cleaned_data.get("senha") or ""
        if criacao or senha:
            alvo.set_password(senha)
        alvo.save()
        registrar_evento(
            evento=RegistroAuditoria.Evento.MUDANCA_USUARIO,
            descricao=f"{'Criação' if criacao else 'Alteração'} do usuário {alvo.username}",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "usuario_id": alvo.pk,
                "username": alvo.username,
                "perfil": alvo.perfil,
                "ativo": alvo.is_active,
                "criacao": criacao,
            },
        )
        if not criacao and perfil_anterior != alvo.perfil:
            registrar_evento(
                evento=RegistroAuditoria.Evento.MUDANCA_PERFIL,
                descricao=f"Perfil de {alvo.username}: {perfil_anterior} → {alvo.perfil}",
                usuario=request.user,
                endereco_ip=obter_ip(request),
                caminho=request.path,
                detalhes={
                    "usuario_id": alvo.pk,
                    "perfil_anterior": perfil_anterior,
                    "perfil_novo": alvo.perfil,
                },
            )
        messages.success(request, "Usuário salvo.")
        return redirect("usuarios:lista")


class AlternarAtivoUsuarioView(PerfilExigidoMixin, View):
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)

    def post(self, request, pk):
        alvo = get_object_or_404(Usuario, pk=pk)
        if alvo.pk == request.user.pk:
            messages.error(request, "Não é possível desativar o próprio usuário.")
            return redirect("usuarios:lista")
        alvo.is_active = not alvo.is_active
        alvo.save(update_fields=["is_active"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.MUDANCA_USUARIO,
            descricao=f"Usuário {alvo.username} {'ativado' if alvo.is_active else 'desativado'}",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"usuario_id": alvo.pk, "ativo": alvo.is_active},
        )
        messages.success(request, "Situação do usuário atualizada.")
        return redirect("usuarios:lista")
