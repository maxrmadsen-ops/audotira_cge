from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.documentos.models import Documento
from aplicacao.instrumentos.models import CampoInstrumento, TermoCongelado, TermoFomento
from aplicacao.instrumentos.conferencia import alerta_do_campo, destino_conferencia
from aplicacao.instrumentos.servico import (
    abrir_nova_versao,
    confirmar_campo,
    congelar_termo,
    corrigir_campo,
    marcar_nao_identificado,
)
from aplicacao.usuarios.acesso import PerfilExigidoMixin, exigir_atuar_na_prestacao
from aplicacao.usuarios.models import Usuario

PERFIS_VALIDACAO = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)


class _TermoAbertoMixin(PerfilExigidoMixin):
    perfis_permitidos = PERFIS_VALIDACAO

    def _termo(self, pk):
        return get_object_or_404(TermoFomento.objects.select_related("documento"), documento_id=pk, documento__excluido_em__isnull=True)


class ValidarCampoTermoView(_TermoAbertoMixin, View):
    def post(self, request, pk, campo_id):
        termo = self._termo(pk)
        exigir_atuar_na_prestacao(request.user, termo.documento.prestacao_contas)
        campo = get_object_or_404(CampoInstrumento, pk=campo_id, termo=termo)
        acao = request.POST.get("acao", "")
        observacao = (request.POST.get("observacao") or "").strip()
        valor = (request.POST.get("valor_validado") or "").strip()
        if acao == "corrigir" and valor != campo.valor_extraido and not observacao:
            messages.error(request, "A correção exige justificativa. O valor extraído permanece.")
            return self._voltar(request, termo)
        if acao == "confirmar" and alerta_do_campo(termo, campo):
            messages.error(
                request,
                "Este campo tem valor monetário incompleto ou divergente. Confira a origem e registre a correção com justificativa. O valor extraído não será substituído.",
            )
            return self._voltar(request, termo)
        try:
            if acao == "confirmar":
                confirmar_campo(campo, request.user, observacao)
                evento = RegistroAuditoria.Evento.CAMPO_CONFIRMADO
            elif acao == "corrigir":
                corrigir_campo(campo, request.user, valor, observacao)
                evento = RegistroAuditoria.Evento.CAMPO_CORRIGIDO
            elif acao == "nao_identificado":
                marcar_nao_identificado(campo, request.user, observacao)
                evento = RegistroAuditoria.Evento.CAMPO_NAO_IDENTIFICADO
            else:
                messages.error(request, "Ação de validação não reconhecida.")
                return self._voltar(request, termo)
        except (TermoCongelado, ValidationError) as exc:
            messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
            return self._voltar(request, termo)
        registrar_evento(
            evento=evento,
            descricao="Validação humana de campo do instrumento",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "documento": pk,
                "prestacao": termo.documento.prestacao_contas_id,
                "campo": campo.nome,
                "status": campo.status,
                "versao": termo.versao,
                "valor_extraido": campo.valor_extraido,
                "valor_validado": campo.valor_validado,
                "modalidade": "individual",
            },
        )
        textos = {
            "confirmar": "Campo confirmado. O valor extraído permanece.",
            "corrigir": "Correção registrada. O valor extraído permanece.",
            "nao_identificado": "Campo marcado como não identificado.",
        }
        messages.success(request, textos[acao])
        return self._voltar(request, termo)

    def _voltar(self, request, termo):
        esperado = reverse("instrumentos:instrumento", args=[termo.documento.prestacao_contas_id])
        if request.POST.get("retorno") == esperado:
            return redirect(destino_conferencia(esperado, request))
        return redirect("documentos:detalhe", pk=termo.documento_id)


class CongelarTermoView(_TermoAbertoMixin, View):
    def post(self, request, pk):
        termo = self._termo(pk)
        exigir_atuar_na_prestacao(request.user, termo.documento.prestacao_contas)
        try:
            congelar_termo(termo, request.user, com_ressalvas=request.POST.get("ressalvas") == "1")
        except (TermoCongelado, ValidationError) as exc:
            messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
            return redirect("documentos:detalhe", pk=pk)
        registrar_evento(
            evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
            descricao="Congelamento da versão estruturada do termo",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"documento": pk, "versao": termo.versao, "hash": termo.hash_congelado},
        )
        messages.success(request, "Versão do termo congelada. Uma alteração posterior abre nova versão.")
        return redirect("documentos:detalhe", pk=pk)


class NovaVersaoTermoView(_TermoAbertoMixin, View):
    def post(self, request, pk):
        termo = self._termo(pk)
        exigir_atuar_na_prestacao(request.user, termo.documento.prestacao_contas)
        try:
            abrir_nova_versao(termo)
        except (TermoCongelado, ValidationError) as exc:
            messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
            return redirect("documentos:detalhe", pk=pk)
        messages.success(request, f"Versão {termo.versao} aberta. A versão congelada anterior permanece.")
        return redirect("documentos:detalhe", pk=pk)


def contexto_termo(documento: Documento) -> dict:
    termo = TermoFomento.objects.filter(documento=documento).select_related("versao_prompt__prompt").first()
    if termo is None:
        return {"termo": None}
    return {
        "termo": termo,
        "partes_termo": termo.partes.all(),
        "clausulas_termo": termo.clausulas.prefetch_related("obrigacoes", "regras_temporais", "referencias_normativas"),
        "obrigacoes_termo": termo.obrigacoes.select_related("clausula"),
        "regras_temporais": termo.regras_temporais.select_related("clausula"),
        "referencias_termo": termo.referencias_normativas.all(),
        "consequencias_termo": termo.consequencias.all(),
        "regras_derivadas": termo.regras_derivadas.all(),
        "campos_termo": termo.campos.all(),
        "aplicacao_termo": _opcional(termo, "aplicacao_financeira"),
        "conta_termo": _opcional(termo, "conta_bancaria"),
        "versoes_termo": termo.versoes_congeladas.order_by("-numero"),
    }


def _opcional(termo, nome: str):
    try:
        return getattr(termo, nome)
    except ObjectDoesNotExist:
        return None
