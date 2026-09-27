from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.documentos.armazenamento import ErroArmazenamento, ler_arquivo, remover_arquivo
from aplicacao.documentos.escolhas import EtapaProcessamento, StatusProcessamento, TipoDocumento
from aplicacao.documentos.formularios import FormularioReprocessamento, FormularioValidacao
from aplicacao.documentos.models import Documento, PaginaDocumento, ReprocessamentoDocumento
from aplicacao.documentos.recebimento import filtrar_documentos, indicadores, receber_arquivo
from aplicacao.documentos.tarefas import processar_documento_task
from aplicacao.documentos.validacao import ErroValidacaoDocumento
from aplicacao.prestacoes_contas.models import PrestacaoContas, PrestacaoParcial
from aplicacao.usuarios.acesso import PerfilExigidoMixin, pode_administrar, pode_executar_analise
from aplicacao.usuarios.models import Usuario

PERFIS_ALTERACAO = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)
ETAPAS_ABERTAS = {
    EtapaProcessamento.RECEBIDO,
    EtapaProcessamento.VALIDANDO_ARQUIVO,
    EtapaProcessamento.EXTRAINDO_TEXTO,
    EtapaProcessamento.EXECUTANDO_OCR,
    EtapaProcessamento.CLASSIFICANDO,
    EtapaProcessamento.EXTRAINDO_METADADOS,
}


def contexto_aba(request, prestacao):
    base = Documento.objects.ativos().filter(prestacao_contas=prestacao)
    consulta = filtrar_documentos(base, request.GET)
    return {
        "documentos": consulta,
        "indicadores_documentos": indicadores(base),
        "filtros_documentos": {
            "q": request.GET.get("q", ""),
            "tipo": request.GET.get("tipo", ""),
            "status": request.GET.get("status", ""),
            "parcial": request.GET.get("parcial", ""),
        },
        "tipos_documento": TipoDocumento.choices,
        "status_documento": StatusProcessamento.choices,
    }


class ListaDocumentosView(LoginRequiredMixin, View):
    def get(self, request):
        base = Documento.objects.ativos()
        consulta = filtrar_documentos(base, request.GET)
        return render(
            request,
            "documentos/lista.html",
            {
                "documentos": consulta[:200],
                "indicadores_documentos": indicadores(base),
                "filtros_documentos": {
                    "q": request.GET.get("q", ""),
                    "tipo": request.GET.get("tipo", ""),
                    "status": request.GET.get("status", ""),
                },
                "tipos_documento": TipoDocumento.choices,
                "status_documento": StatusProcessamento.choices,
            },
        )


class EnviarDocumentosView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_ALTERACAO

    def post(self, request, prestacao_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_pk)
        arquivos = request.FILES.getlist("arquivos")
        if not arquivos:
            messages.error(request, "Selecione ao menos um arquivo PDF.")
            return self._voltar(prestacao.pk)
        parcial = self._parcial(prestacao, request.POST.get("prestacao_parcial"))
        for arquivo in arquivos:
            try:
                _documento, duplicados = receber_arquivo(
                    prestacao=prestacao,
                    arquivo=arquivo,
                    usuario=request.user,
                    parcial=parcial,
                    request=request,
                )
            except ErroValidacaoDocumento as exc:
                messages.error(request, f"{arquivo.name}: {exc.mensagem}")
                continue
            if duplicados:
                messages.warning(
                    request,
                    f"{arquivo.name}: o mesmo arquivo já existe em outro registro. O envio foi mantido e a ocorrência foi registrada.",
                )
            else:
                messages.success(request, f"{arquivo.name} recebido. O processamento continua em segundo plano.")
        return self._voltar(prestacao.pk)

    def _parcial(self, prestacao, valor):
        if not valor:
            return None
        return PrestacaoParcial.objects.filter(pk=valor, prestacao=prestacao).first()

    def _voltar(self, pk):
        return redirect(f"{reverse('prestacoes_contas:detalhe', kwargs={'pk': pk})}?aba=documentos")


class DetalheDocumentoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        documento = self._documento(request, pk)
        try:
            pagina_inicial = int(request.GET.get("pagina") or 1)
        except (TypeError, ValueError):
            pagina_inicial = 1
        if pagina_inicial < 1:
            pagina_inicial = 1
        return render(
            request,
            "documentos/detalhe.html",
            {
                "documento": documento,
                "pagina_inicial": pagina_inicial,
                "paginas": documento.paginas.all(),
                "dados": documento.dados_extraidos.select_related("pagina"),
                "form_validacao": FormularioValidacao(documento=documento),
                "form_reprocessamento": FormularioReprocessamento(),
                "pode_alterar": pode_executar_analise(request.user),
                "pode_excluir": pode_administrar(request.user),
                "acompanhar": documento.etapa in ETAPAS_ABERTAS,
            },
        )

    def _documento(self, request, pk):
        consulta = Documento.objects.select_related("prestacao_contas", "prestacao_parcial", "validado_por")
        if not pode_administrar(request.user):
            consulta = consulta.ativos()
        return get_object_or_404(consulta, pk=pk)


class ArquivoDocumentoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        documento = get_object_or_404(Documento.objects.ativos(), pk=pk)
        try:
            caminho = ler_arquivo(documento.nome_armazenado)
        except ErroArmazenamento as exc:
            raise Http404(exc.mensagem) from exc
        resposta = FileResponse(caminho.open("rb"), content_type="application/pdf")
        resposta["Content-Disposition"] = "inline"
        resposta["X-Content-Type-Options"] = "nosniff"
        return resposta


class TextoPaginaView(LoginRequiredMixin, View):
    def get(self, request, pk, numero):
        pagina = get_object_or_404(
            PaginaDocumento.objects.select_related("documento"),
            documento_id=pk,
            numero_pagina=numero,
            documento__excluido_em__isnull=True,
        )
        return JsonResponse(
            {
                "numero": pagina.numero_pagina,
                "texto": pagina.texto_extraido,
                "metodo": pagina.get_metodo_extracao_display(),
                "qualidade": pagina.get_qualidade_extracao_display(),
                "necessitou_ocr": pagina.necessitou_ocr,
                "ocr_executado": pagina.ocr_executado,
            }
        )


class StatusDocumentoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        documento = get_object_or_404(Documento.objects.ativos(), pk=pk)
        return JsonResponse(
            {
                "status": documento.status_processamento,
                "status_rotulo": documento.get_status_processamento_display(),
                "etapa": documento.etapa,
                "etapa_rotulo": documento.get_etapa_display(),
                "erro": documento.erro_processamento,
                "acompanhar": documento.etapa in ETAPAS_ABERTAS,
            }
        )


class ValidarDocumentoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_ALTERACAO

    def post(self, request, pk):
        documento = get_object_or_404(Documento.objects.ativos(), pk=pk)
        formulario = FormularioValidacao(request.POST, documento=documento)
        if not formulario.is_valid():
            messages.error(request, "Não foi possível validar a classificação.")
            return redirect("documentos:detalhe", pk=pk)
        tipo_anterior = documento.tipo_documento
        documento.tipo_documento = formulario.cleaned_data["tipo_documento"]
        documento.subtipo_documento = formulario.cleaned_data["subtipo_documento"]
        documento.prestacao_parcial = formulario.cleaned_data["prestacao_parcial"]
        documento.data_documento = formulario.cleaned_data["data_documento"]
        documento.classificacao_validada = True
        documento.validado_por = request.user
        documento.validado_em = timezone.now()
        documento.status_processamento = StatusProcessamento.VALIDADO
        documento.etapa = EtapaProcessamento.CONCLUIDO
        documento.save()
        evento = (
            RegistroAuditoria.Evento.RECLASSIFICACAO
            if tipo_anterior != documento.tipo_documento
            else RegistroAuditoria.Evento.VALIDACAO_HUMANA
        )
        registrar_evento(
            evento=evento,
            descricao="Validação humana da classificação",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "documento": documento.pk,
                "tipo_anterior": tipo_anterior,
                "tipo_final": documento.tipo_documento,
                "classificacao_original": documento.classificacao_original,
            },
        )
        messages.success(request, "Classificação registrada. A sugestão original do sistema foi preservada.")
        return redirect("documentos:detalhe", pk=pk)


class ReprocessarDocumentoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_ALTERACAO

    def post(self, request, pk):
        documento = get_object_or_404(Documento.objects.ativos(), pk=pk)
        formulario = FormularioReprocessamento(request.POST)
        motivo = formulario.cleaned_data.get("motivo", "") if formulario.is_valid() else ""
        registro = ReprocessamentoDocumento.objects.create(documento=documento, solicitado_por=request.user, motivo=motivo)
        documento.status_processamento = StatusProcessamento.RECEBIDO
        documento.etapa = EtapaProcessamento.RECEBIDO
        documento.erro_processamento = ""
        documento.save(update_fields=["status_processamento", "etapa", "erro_processamento", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.REPROCESSAMENTO,
            descricao="Reprocessamento solicitado",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"documento": documento.pk, "reprocessamento": registro.pk},
        )
        processar_documento_task.delay(documento.pk, request.user.pk, registro.pk)
        messages.success(request, "Reprocessamento solicitado.")
        return redirect("documentos:detalhe", pk=pk)


class ArquivarDocumentoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_ALTERACAO

    def post(self, request, pk):
        documento = get_object_or_404(Documento.objects.ativos(), pk=pk)
        documento.excluido_em = timezone.now()
        documento.status_processamento = StatusProcessamento.ARQUIVADO
        documento.save(update_fields=["excluido_em", "status_processamento", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.EXCLUSAO,
            descricao="Arquivamento lógico de documento",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"documento": documento.pk, "fisico": False},
        )
        messages.success(request, "Documento arquivado. O arquivo físico foi preservado.")
        return redirect("prestacoes_contas:detalhe", pk=documento.prestacao_contas_id)


class ExcluirDocumentoView(PerfilExigidoMixin, View):
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)

    def post(self, request, pk):
        documento = get_object_or_404(Documento, pk=pk)
        if request.POST.get("confirmacao") != "EXCLUIR":
            messages.error(request, "Confirme a exclusão física digitando EXCLUIR.")
            return redirect("documentos:detalhe", pk=pk)
        prestacao_id = documento.prestacao_contas_id
        identificador = documento.pk
        remover_arquivo(documento.nome_armazenado)
        documento.delete()
        registrar_evento(
            evento=RegistroAuditoria.Evento.EXCLUSAO,
            descricao="Exclusão física de documento",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"documento": identificador, "fisico": True},
        )
        messages.success(request, "Documento excluído fisicamente.")
        return redirect("prestacoes_contas:detalhe", pk=prestacao_id)
