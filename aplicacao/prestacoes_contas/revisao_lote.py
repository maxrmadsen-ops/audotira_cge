"""Confirmação em lote de itens elegíveis. Não aprova a prestação."""

import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.situacao_revisao import avaliar_lote, chaves_ratificacao


def preparar_lote(plano, identificadores: list[str]) -> dict:
    chaves = chaves_ratificacao(plano.prestacao)
    pedidos = []
    for valor in identificadores:
        if str(valor).isdigit():
            pedidos.append(int(valor))
    itens = {item.pk: item for item in plano.itens.all()}
    elegiveis = []
    bloqueados = []
    for pk in dict.fromkeys(pedidos):
        item = itens.get(pk)
        if item is None:
            bloqueados.append({"id": pk, "motivo": "Item não pertence a este plano."})
            continue
        pode, motivo = avaliar_lote(item, chaves)
        if pode:
            elegiveis.append(item)
        else:
            bloqueados.append({"id": item.pk, "ordem": item.ordem, "motivo": motivo})
    return {
        "elegiveis": elegiveis,
        "bloqueados": bloqueados,
        "quantidade_selecionada": len(dict.fromkeys(pedidos)),
        "quantidade_elegivel": len(elegiveis),
        "quantidade_bloqueada": len(bloqueados),
    }


def confirmar_itens_elegiveis(*, plano, usuario, identificadores: list[str], request=None) -> dict:
    preparo = preparar_lote(plano, identificadores)
    if not preparo["elegiveis"]:
        return {**preparo, "confirmados": [], "operacao": ""}
    operacao = uuid.uuid4().hex
    agora = timezone.now()
    with transaction.atomic():
        confirmados = []
        for item in preparo["elegiveis"]:
            atual = type(item).objects.select_for_update().get(pk=item.pk, plano=plano)
            pode, motivo = avaliar_lote(atual, chaves_ratificacao(plano.prestacao))
            if not pode:
                preparo["bloqueados"].append({"id": atual.pk, "ordem": atual.ordem, "motivo": motivo})
                continue
            atual.status_revisao = StatusRevisaoPlano.CONFIRMADO
            atual.revisado_por = usuario
            atual.revisado_em = agora
            atual.save(update_fields=["status_revisao", "revisado_por", "revisado_em", "atualizado_em"])
            registrar_evento(
                evento=RegistroAuditoria.Evento.REVISAO_HUMANA,
                descricao="Item confirmado em lote. A prestação de contas não foi aprovada.",
                usuario=usuario,
                endereco_ip=obter_ip(request),
                caminho=getattr(request, "path", ""),
                detalhes={
                    "prestacao": plano.prestacao.numero_processo,
                    "plano": plano.pk,
                    "item": atual.pk,
                    "ordem": atual.ordem,
                    "operacao_lote": operacao,
                    "acao": "confirmar_itens_elegiveis",
                },
            )
            confirmados.append(atual.pk)
        registrar_evento(
            evento=RegistroAuditoria.Evento.REVISAO_HUMANA,
            descricao="Operação de confirmação em lote de itens elegíveis.",
            usuario=usuario,
            endereco_ip=obter_ip(request),
            caminho=getattr(request, "path", ""),
            detalhes={
                "prestacao": plano.prestacao.numero_processo,
                "plano": plano.pk,
                "operacao_lote": operacao,
                "confirmados": confirmados,
                "bloqueados": preparo["bloqueados"],
                "aprovacao_administrativa": False,
            },
        )
    preparo["confirmados"] = confirmados
    preparo["operacao"] = operacao
    preparo["quantidade_elegivel"] = len(confirmados)
    preparo["quantidade_bloqueada"] = len(preparo["bloqueados"])
    return preparo


class RevisaoLotePlanoView(LoginRequiredMixin, View):
    def post(self, request, pk, plano_pk):
        from aplicacao.prestacoes_contas.apresentacao_plano import url_workspace
        from aplicacao.prestacoes_contas.models import PlanoTrabalho, PrestacaoContas
        from aplicacao.usuarios.acesso import exigir_atuar_na_prestacao, exigir_ver_prestacao

        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        plano = get_object_or_404(PlanoTrabalho, pk=plano_pk, prestacao=prestacao)
        exigir_ver_prestacao(request.user, prestacao)
        exigir_atuar_na_prestacao(request.user, prestacao)
        if request.POST.get("confirmar_lote") != "1":
            messages.error(request, "A confirmação em lote exige a ação explícita Confirmar itens elegíveis.")
        else:
            resultado = confirmar_itens_elegiveis(
                plano=plano,
                usuario=request.user,
                identificadores=request.POST.getlist("item"),
                request=request,
            )
            if resultado["confirmados"]:
                messages.success(
                    request,
                    f"{len(resultado['confirmados'])} item(ns) elegível(is) confirmado(s). A prestação de contas não foi aprovada.",
                )
            if resultado["bloqueados"]:
                messages.warning(request, f"{len(resultado['bloqueados'])} item(ns) não entraram no lote.")
            if not resultado["confirmados"] and not resultado["bloqueados"]:
                messages.error(request, "Nenhum item foi selecionado.")
        return redirect(url_workspace(prestacao, plano, request.POST, acao="confirmar_itens_elegiveis"))
