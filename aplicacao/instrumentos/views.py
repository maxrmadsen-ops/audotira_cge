from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.documentos.models import Documento
from aplicacao.instrumentos.models import CampoInstrumento, TermoCongelado, TermoFomento
from aplicacao.instrumentos.servico import (
    abrir_nova_versao,
    confirmar_campo,
    congelar_termo,
    corrigir_campo,
    marcar_nao_identificado,
)
from aplicacao.usuarios.acesso import PerfilExigidoMixin
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
        campo = get_object_or_404(CampoInstrumento, pk=campo_id, termo=termo)
        acao = request.POST.get("acao", "")
        observacao = (request.POST.get("observacao") or "").strip()
        try:
            if acao == "confirmar":
                confirmar_campo(campo, request.user, observacao)
            elif acao == "corrigir":
                corrigir_campo(campo, request.user, (request.POST.get("valor_validado") or "").strip(), observacao)
            elif acao == "nao_identificado":
                marcar_nao_identificado(campo, request.user, observacao)
            else:
                messages.error(request, "Ação de validação não reconhecida.")
                return redirect("documentos:detalhe", pk=pk)
        except (TermoCongelado, ValidationError) as exc:
            messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
            return redirect("documentos:detalhe", pk=pk)
        registrar_evento(
            evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
            descricao="Validação humana de campo do termo",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"documento": pk, "campo": campo.nome, "status": campo.status},
        )
        messages.success(request, "Validação do campo registrada. O valor extraído foi preservado.")
        return redirect("documentos:detalhe", pk=pk)


class CongelarTermoView(_TermoAbertoMixin, View):
    def post(self, request, pk):
        termo = self._termo(pk)
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
