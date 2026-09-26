from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, UpdateView

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.documentos.validacao import ErroValidacaoDocumento, validar_envio
from aplicacao.normas.armazenamento import armazenar_pdf, ler_arquivo
from aplicacao.normas.escolhas import SituacaoNorma, TipoNorma
from aplicacao.normas.formularios import (
    FormularioAplicabilidade,
    FormularioNorma,
    FormularioPesquisaNormativa,
    FormularioRelacionamento,
)
from aplicacao.normas.models import ConsultaNormativa, Norma, ReprocessamentoNorma, ResultadoConsultaNormativa
from aplicacao.normas.recuperador import RecuperadorNormativo
from aplicacao.normas.servico import criar_nova_versao
from aplicacao.normas.tarefas import processar_norma_task
from aplicacao.usuarios.acesso import PerfilExigidoMixin
from aplicacao.usuarios.models import Usuario

PERFIS_LEITURA = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
    Usuario.Perfil.CONSULTA,
)
PERFIS_EDICAO = (Usuario.Perfil.ADMINISTRADOR,)


class ListaNormasView(PerfilExigidoMixin, ListView):
    model = Norma
    template_name = "normas/lista.html"
    context_object_name = "normas"
    perfis_permitidos = PERFIS_LEITURA

    def get_queryset(self):
        consulta = Norma.objects.filter(desativada_em__isnull=True)
        tipo = self.request.GET.get("tipo", "")
        numero = self.request.GET.get("numero", "").strip()
        ano = self.request.GET.get("ano", "").strip()
        orgao = self.request.GET.get("orgao", "").strip()
        situacao = self.request.GET.get("situacao", "")
        vigencia = self.request.GET.get("vigencia", "")
        if tipo:
            consulta = consulta.filter(tipo_norma=tipo)
        if numero:
            consulta = consulta.filter(numero__icontains=numero)
        if ano.isdigit():
            consulta = consulta.filter(ano=int(ano))
        if orgao:
            consulta = consulta.filter(orgao_emissor__icontains=orgao)
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        hoje = timezone.localdate()
        if vigencia == "vigente":
            consulta = consulta.filter(inicio_vigencia__lte=hoje).filter(
                Q(fim_vigencia__isnull=True) | Q(fim_vigencia__gte=hoje)
            )
        elif vigencia == "encerrada":
            consulta = consulta.filter(fim_vigencia__lt=hoje)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["tipos_norma"] = TipoNorma.choices
        contexto["situacoes"] = SituacaoNorma.choices
        contexto["filtros"] = {
            "tipo": self.request.GET.get("tipo", ""),
            "numero": self.request.GET.get("numero", ""),
            "ano": self.request.GET.get("ano", ""),
            "orgao": self.request.GET.get("orgao", ""),
            "situacao": self.request.GET.get("situacao", ""),
            "vigencia": self.request.GET.get("vigencia", ""),
        }
        contexto["pode_alterar"] = self.request.user.perfil in PERFIS_EDICAO
        return contexto


class CriarNormaView(PerfilExigidoMixin, FormView):
    template_name = "normas/formulario.html"
    form_class = FormularioNorma
    perfis_permitidos = PERFIS_EDICAO

    def get_form_kwargs(self):
        dados = super().get_form_kwargs()
        dados["exigir_arquivo"] = True
        return dados

    def form_valid(self, form):
        arquivo = self.request.FILES["arquivo"]
        conteudo = arquivo.read()
        try:
            info = validar_envio(arquivo.name, conteudo, arquivo.content_type or "")
        except ErroValidacaoDocumento as exc:
            form.add_error("arquivo", exc.mensagem)
            return self.form_invalid(form)
        norma = form.save(commit=False)
        norma.criado_por = self.request.user
        norma.hash_sha256 = info["hash_sha256"]
        norma.nome_original = arquivo.name
        norma.save()
        norma.arquivo = armazenar_pdf(norma.pk, conteudo)
        norma.save(update_fields=["arquivo", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.CRIACAO,
            descricao="Norma cadastrada.",
            usuario=self.request.user,
            caminho=self.request.path,
            detalhes={"norma_id": norma.id, "hash_sha256": norma.hash_sha256, "versao": norma.versao},
        )
        processar_norma_task.delay(norma.id, self.request.user.id)
        messages.success(self.request, "Norma recebida. O processamento ocorre em segundo plano.")
        return HttpResponseRedirect(reverse("normas:detalhe", args=[norma.pk]))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = "Cadastrar norma"
        return contexto


class DetalheNormaView(PerfilExigidoMixin, DetailView):
    model = Norma
    template_name = "normas/detalhe.html"
    context_object_name = "norma"
    perfis_permitidos = PERFIS_LEITURA

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        norma = self.object
        contexto["pode_alterar"] = self.request.user.perfil in PERFIS_EDICAO
        contexto["formulario_aplicabilidade"] = FormularioAplicabilidade()
        contexto["formulario_relacionamento"] = FormularioRelacionamento(norma=norma)
        contexto["versoes"] = Norma.objects.filter(grupo_id=norma.grupo_id).order_by("versao")
        return contexto


class EditarNormaView(PerfilExigidoMixin, UpdateView):
    model = Norma
    form_class = FormularioNorma
    template_name = "normas/formulario.html"
    perfis_permitidos = PERFIS_EDICAO

    def get_form_kwargs(self):
        dados = super().get_form_kwargs()
        dados["exigir_arquivo"] = False
        return dados

    def form_valid(self, form):
        anterior = Norma.objects.get(pk=self.object.pk)
        vigencia_mudou = (
            form.cleaned_data["inicio_vigencia"] != anterior.inicio_vigencia
            or form.cleaned_data["fim_vigencia"] != anterior.fim_vigencia
            or form.cleaned_data["situacao"] != anterior.situacao
        )
        if vigencia_mudou and (
            anterior.trechos.exists() or ResultadoConsultaNormativa.objects.filter(trecho__norma=anterior).exists()
        ):
            nova = criar_nova_versao(anterior, usuario=self.request.user, dados=form.cleaned_data)
            messages.success(self.request, "A vigência foi preservada numa nova versão. A anterior permanece consultável.")
            return HttpResponseRedirect(reverse("normas:detalhe", args=[nova.pk]))
        form.save()
        registrar_evento(
            evento=RegistroAuditoria.Evento.ALTERACAO,
            descricao="Metadados da norma alterados.",
            usuario=self.request.user,
            caminho=self.request.path,
            detalhes={"norma_id": self.object.id, "hash_sha256": self.object.hash_sha256},
        )
        messages.success(self.request, "Metadados atualizados.")
        return HttpResponseRedirect(reverse("normas:detalhe", args=[self.object.pk]))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = "Editar norma"
        return contexto


class NovaVersaoView(PerfilExigidoMixin, DetailView):
    model = Norma
    perfis_permitidos = PERFIS_EDICAO
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        norma = self.get_object()
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            messages.error(request, "Envie o PDF da nova versão.")
            return HttpResponseRedirect(reverse("normas:detalhe", args=[norma.pk]))
        conteudo = arquivo.read()
        try:
            nova = criar_nova_versao(norma, usuario=request.user, conteudo=conteudo, nome_original=arquivo.name)
        except ErroValidacaoDocumento as exc:
            messages.error(request, exc.mensagem)
            return HttpResponseRedirect(reverse("normas:detalhe", args=[norma.pk]))
        processar_norma_task.delay(nova.id, request.user.id)
        messages.success(request, "Nova versão registrada. A versão anterior foi preservada.")
        return HttpResponseRedirect(reverse("normas:detalhe", args=[nova.pk]))


class ReprocessarNormaView(PerfilExigidoMixin, DetailView):
    model = Norma
    perfis_permitidos = PERFIS_EDICAO
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        norma = self.get_object()
        registro = ReprocessamentoNorma.objects.create(norma=norma, solicitado_por=request.user, motivo="Reprocessamento solicitado")
        registrar_evento(
            evento=RegistroAuditoria.Evento.REPROCESSAMENTO,
            descricao="Reprocessamento de norma solicitado.",
            usuario=request.user,
            caminho=request.path,
            detalhes={"norma_id": norma.id, "hash_sha256": norma.hash_sha256},
        )
        processar_norma_task.delay(norma.id, request.user.id, registro.id)
        messages.success(request, "Reprocessamento solicitado.")
        return HttpResponseRedirect(reverse("normas:detalhe", args=[norma.pk]))


class DesativarNormaView(PerfilExigidoMixin, DetailView):
    model = Norma
    perfis_permitidos = PERFIS_EDICAO
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        norma = self.get_object()
        norma.desativada_em = timezone.now()
        norma.save(update_fields=["desativada_em", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.ALTERACAO,
            descricao="Norma desativada.",
            usuario=request.user,
            caminho=request.path,
            detalhes={"norma_id": norma.id, "hash_sha256": norma.hash_sha256},
        )
        messages.success(request, "Norma desativada. O histórico permanece.")
        return HttpResponseRedirect(reverse("normas:lista"))


class AplicabilidadeView(PerfilExigidoMixin, DetailView):
    model = Norma
    perfis_permitidos = PERFIS_EDICAO
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        norma = self.get_object()
        formulario = FormularioAplicabilidade(request.POST)
        if formulario.is_valid():
            item = formulario.save(commit=False)
            item.norma = norma
            item.save()
            registrar_evento(
                evento=RegistroAuditoria.Evento.ALTERACAO,
                descricao="Aplicabilidade da norma definida.",
                usuario=request.user,
                caminho=request.path,
                detalhes={"norma_id": norma.id, "aplicabilidade_id": item.id},
            )
            messages.success(request, "Aplicabilidade registrada.")
        else:
            messages.error(request, "Não foi possível registrar a aplicabilidade.")
        return HttpResponseRedirect(reverse("normas:detalhe", args=[norma.pk]))


class RelacionamentoView(PerfilExigidoMixin, DetailView):
    model = Norma
    perfis_permitidos = PERFIS_EDICAO
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        norma = self.get_object()
        formulario = FormularioRelacionamento(request.POST, norma=norma)
        if formulario.is_valid() and formulario.cleaned_data["destino"].pk != norma.pk:
            item = formulario.save(commit=False)
            item.origem = norma
            item.criado_por = request.user
            item.save()
            registrar_evento(
                evento=RegistroAuditoria.Evento.ALTERACAO,
                descricao="Relacionamento entre normas registrado.",
                usuario=request.user,
                caminho=request.path,
                detalhes={"norma_id": norma.id, "destino_id": item.destino_id, "tipo": item.tipo},
            )
            messages.success(request, "Relacionamento registrado. Ele não altera a vigência automaticamente.")
        else:
            messages.error(request, "Não foi possível registrar o relacionamento.")
        return HttpResponseRedirect(reverse("normas:detalhe", args=[norma.pk]))


class ArquivoNormaView(PerfilExigidoMixin, DetailView):
    model = Norma
    perfis_permitidos = PERFIS_LEITURA

    def get(self, request, *args, **kwargs):
        norma = self.get_object()
        caminho = ler_arquivo(norma.arquivo)
        resposta = FileResponse(caminho.open("rb"), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{norma.nome_original or "norma.pdf"}"'
        return resposta


class PesquisaNormativaView(PerfilExigidoMixin, FormView):
    template_name = "normas/pesquisa.html"
    form_class = FormularioPesquisaNormativa
    perfis_permitidos = PERFIS_LEITURA

    def form_valid(self, form):
        consulta = RecuperadorNormativo().recuperar(
            texto=form.cleaned_data["texto"],
            data_referencia=form.cleaned_data["data_referencia"],
            tipo_instrumento=form.cleaned_data["tipo_instrumento"],
            orgao=form.cleaned_data["orgao"],
            tipo_prestacao=form.cleaned_data["tipo_prestacao"],
            categoria=form.cleaned_data["categoria"],
            prestacao_contas=form.cleaned_data["prestacao_contas"],
            usuario=self.request.user,
        )
        registrar_evento(
            evento=RegistroAuditoria.Evento.CONSULTA_NORMATIVA,
            descricao="Consulta normativa registrada.",
            usuario=self.request.user,
            caminho=self.request.path,
            detalhes={
                "consulta_id": consulta.id,
                "data_referencia": consulta.data_referencia.isoformat(),
                "resultados": consulta.resultados.count(),
            },
        )
        return HttpResponseRedirect(reverse("normas:consulta", args=[consulta.pk]))


class ConsultaNormativaView(PerfilExigidoMixin, DetailView):
    model = ConsultaNormativa
    template_name = "normas/consulta.html"
    context_object_name = "consulta"
    perfis_permitidos = PERFIS_LEITURA

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        consideradas = self.object.normas_consideradas or []
        contexto["elegiveis"] = [item for item in consideradas if item.get("elegivel")]
        contexto["descartadas"] = [item for item in consideradas if not item.get("elegivel")]
        contexto["resultados"] = self.object.resultados.select_related("trecho", "trecho__norma")
        return contexto
