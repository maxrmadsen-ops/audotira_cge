"""Revisão humana do plano extraído. Nada entra como dado definitivo sem esta tela."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.prestacoes_contas.escolhas import NaturezaItem, StatusRevisaoPlano
from aplicacao.prestacoes_contas.extracao_plano import data_br, dinheiro
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, Meta, PlanoTrabalho, PrestacaoContas
from aplicacao.usuarios.acesso import exigir_atuar_na_prestacao, exigir_ver_prestacao, pode_atuar_na_prestacao

CAMPOS_IDENTIFICACAO = (
    ("titulo", "Título"),
    ("objeto", "Objeto"),
    ("finalidade", "Finalidade"),
    ("transferencia", "Transferência"),
    ("proponente", "Proponente"),
    ("unidade_gestora", "Unidade gestora"),
    ("publico_alvo", "Público alvo"),
    ("situacao_informada", "Situação informada"),
)


def pendencias(plano: PlanoTrabalho) -> list[str]:
    itens = []
    if plano.status_revisao == StatusRevisaoPlano.AGUARDANDO:
        itens.append("Identificação da parceria aguarda confirmação.")
    if plano.cronograma_status == StatusRevisaoPlano.AGUARDANDO and plano.cronograma:
        itens.append("Cronograma de desembolso aguarda confirmação.")
    for nome, rotulo in CAMPOS_IDENTIFICACAO:
        if not getattr(plano, nome):
            itens.append(f"{rotulo} não localizado no documento.")
    if plano.vigencia_inicio is None or plano.vigencia_fim is None:
        itens.append("Período de execução incompleto.")
    for meta in plano.metas.all():
        if meta.status_revisao == StatusRevisaoPlano.AGUARDANDO:
            itens.append(f"Meta «{meta.descricao[:80]}» aguarda confirmação.")
    for item in plano.itens.all():
        if item.status_revisao == StatusRevisaoPlano.AGUARDANDO:
            itens.append(f"Item {item.ordem} aguarda confirmação.")
        if item.valor_previsto is None or item.quantidade is None:
            itens.append(f"Item {item.ordem} está sem quantidade ou valor total.")
    return itens


class RevisaoPlanoView(LoginRequiredMixin, View):
    def get(self, request, pk, plano_pk):
        prestacao, plano = self._carregar(request, pk, plano_pk)
        exigir_ver_prestacao(request.user, prestacao)
        return render(request, "prestacoes_contas/revisao_plano.html", self._contexto(request, prestacao, plano))

    def post(self, request, pk, plano_pk):
        prestacao, plano = self._carregar(request, pk, plano_pk)
        exigir_ver_prestacao(request.user, prestacao)
        exigir_atuar_na_prestacao(request.user, prestacao)
        acao = request.POST.get("acao") or ""
        tratado = {
            "confirmar_plano": self._confirmar_plano,
            "corrigir_plano": self._corrigir_plano,
            "confirmar_cronograma": self._confirmar_cronograma,
            "corrigir_cronograma": self._corrigir_cronograma,
            "confirmar_meta": self._confirmar_meta,
            "corrigir_meta": self._corrigir_meta,
            "confirmar_item": self._confirmar_item,
            "corrigir_item": self._corrigir_item,
        }.get(acao)
        if tratado is None:
            messages.error(request, "Ação de revisão não reconhecida.")
        else:
            tratado(request, prestacao, plano)
        return redirect("prestacoes_contas:revisao_plano", pk=prestacao.pk, plano_pk=plano.pk)

    def _carregar(self, request, pk, plano_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        plano = get_object_or_404(
            PlanoTrabalho.objects.prefetch_related("itens", "metas"),
            pk=plano_pk,
            prestacao=prestacao,
        )
        return prestacao, plano

    def _contexto(self, request, prestacao, plano):
        anos = []
        for linha in plano.cronograma or []:
            if linha.get("ano") not in anos:
                anos.append(linha.get("ano"))
        return {
            "prestacao": prestacao,
            "plano": plano,
            "pode_alterar": pode_atuar_na_prestacao(request.user, prestacao),
            "pendencias": pendencias(plano),
            "naturezas": NaturezaItem.choices,
            "anos_cronograma": anos,
            "total_extraido": plano.valor_extraido,
            "total_confirmado": plano.valor_previsto,
        }

    def _confirmar_plano(self, request, prestacao, plano):
        self._marcar(plano, request.user, StatusRevisaoPlano.CONFIRMADO)
        plano.save(update_fields=["status_revisao", "revisado_por", "revisado_em", "atualizado_em"])
        self._auditar(request, prestacao, plano, "confirmar_plano")
        messages.success(request, "Identificação confirmada. Os demais campos continuam pendentes.")

    def _corrigir_plano(self, request, prestacao, plano):
        plano.titulo = (request.POST.get("titulo") or "").strip()[:255] or plano.titulo
        for nome, _rotulo in CAMPOS_IDENTIFICACAO:
            if nome == "titulo":
                continue
            setattr(plano, nome, (request.POST.get(nome) or "").strip())
        inicio = data_br(request.POST.get("vigencia_inicio") or "") or _data_iso(request.POST.get("vigencia_inicio"))
        fim = data_br(request.POST.get("vigencia_fim") or "") or _data_iso(request.POST.get("vigencia_fim"))
        plano.vigencia_inicio = inicio
        plano.vigencia_fim = fim
        for nome in ("valor_global", "valor_repasse", "valor_contrapartida"):
            numero, valido = _dinheiro_post(request.POST.get(nome))
            if not valido:
                messages.error(request, "Valor monetário inválido na identificação.")
                return
            setattr(plano, nome, numero)
        self._marcar(plano, request.user, StatusRevisaoPlano.CORRIGIDO)
        plano.save()
        self._auditar(request, prestacao, plano, "corrigir_plano")
        messages.success(request, "Identificação corrigida. Metas e itens não foram alterados.")

    def _confirmar_cronograma(self, request, prestacao, plano):
        plano.cronograma_status = StatusRevisaoPlano.CONFIRMADO
        plano.save(update_fields=["cronograma_status", "atualizado_em"])
        self._auditar(request, prestacao, plano, "confirmar_cronograma")
        messages.success(request, "Cronograma confirmado.")

    def _corrigir_cronograma(self, request, prestacao, plano):
        repasses = request.POST.getlist("repasse")
        contrapartidas = request.POST.getlist("contrapartida")
        linhas = list(plano.cronograma or [])
        if len(repasses) != len(linhas) or len(contrapartidas) != len(linhas):
            messages.error(request, "O cronograma enviado não corresponde às linhas extraídas.")
            return
        novo = []
        for linha, repasse, contrapartida in zip(linhas, repasses, contrapartidas):
            valor_repasse, repasse_valido = _dinheiro_post(repasse)
            valor_contrapartida, contrapartida_valida = _dinheiro_post(contrapartida)
            if not repasse_valido or not contrapartida_valida:
                messages.error(request, "Há valor inválido no cronograma.")
                return
            atualizada = dict(linha)
            atualizada["repasse"] = str(valor_repasse or "")
            atualizada["contrapartida"] = str(valor_contrapartida or "")
            novo.append(atualizada)
        plano.cronograma = novo
        plano.cronograma_status = StatusRevisaoPlano.CORRIGIDO
        plano.save(update_fields=["cronograma", "cronograma_status", "atualizado_em"])
        self._auditar(request, prestacao, plano, "corrigir_cronograma")
        messages.success(request, "Cronograma corrigido.")

    def _confirmar_meta(self, request, prestacao, plano):
        meta = self._meta(plano, request.POST.get("meta_id"))
        if meta is None:
            messages.error(request, "Meta não encontrada neste plano.")
            return
        self._marcar(meta, request.user, StatusRevisaoPlano.CONFIRMADO)
        meta.save(update_fields=["status_revisao", "revisado_por", "revisado_em", "atualizado_em"])
        self._auditar(request, prestacao, plano, "confirmar_meta", meta=meta)
        messages.success(request, "Meta confirmada. Os outros registros permanecem como estavam.")

    def _corrigir_meta(self, request, prestacao, plano):
        meta = self._meta(plano, request.POST.get("meta_id"))
        if meta is None:
            messages.error(request, "Meta não encontrada neste plano.")
            return
        descricao = (request.POST.get("descricao") or "").strip()
        if not descricao:
            messages.error(request, "A descrição da meta não pode ficar vazia.")
            return
        meta.descricao = descricao
        meta.forma_execucao = (request.POST.get("forma_execucao") or "").strip()
        meta.parametros_afericao = (request.POST.get("parametros_afericao") or "").strip()
        meta.etapas = (request.POST.get("etapas") or "").strip()
        meta.indicador = meta.parametros_afericao[:255]
        meta.periodo_inicio = data_br(request.POST.get("periodo_inicio") or "") or _data_iso(request.POST.get("periodo_inicio"))
        meta.periodo_fim = data_br(request.POST.get("periodo_fim") or "") or _data_iso(request.POST.get("periodo_fim"))
        self._marcar(meta, request.user, StatusRevisaoPlano.CORRIGIDO)
        meta.save()
        self._auditar(request, prestacao, plano, "corrigir_meta", meta=meta)
        messages.success(request, "Meta corrigida. A descrição original foi preservada.")

    def _confirmar_item(self, request, prestacao, plano):
        item = self._item(plano, request.POST.get("item_id"))
        if item is None:
            messages.error(request, "Item não encontrado neste plano.")
            return
        self._marcar(item, request.user, StatusRevisaoPlano.CONFIRMADO)
        item.save(update_fields=["status_revisao", "revisado_por", "revisado_em", "atualizado_em"])
        self._auditar(request, prestacao, plano, "confirmar_item", item=item)
        messages.success(request, "Item confirmado. Os demais itens continuam pendentes.")

    def _corrigir_item(self, request, prestacao, plano):
        item = self._item(plano, request.POST.get("item_id"))
        if item is None:
            messages.error(request, "Item não encontrado neste plano.")
            return
        descricao = (request.POST.get("descricao") or "").strip()
        if not descricao:
            messages.error(request, "A descrição do item não pode ficar vazia.")
            return
        quantidade, quantidade_valida = _dinheiro_post(request.POST.get("quantidade"))
        unitario, unitario_valido = _dinheiro_post(request.POST.get("valor_unitario"))
        total, total_valido = _dinheiro_post(request.POST.get("valor_previsto"), obrigatorio=True)
        if not quantidade_valida or not unitario_valido or not total_valido:
            messages.error(request, "Quantidade ou valor do item é inválido.")
            return
        natureza = request.POST.get("natureza") or item.natureza
        if natureza not in NaturezaItem.values:
            messages.error(request, "Natureza do item não reconhecida.")
            return
        item.descricao = descricao
        item.quantidade = quantidade
        item.unidade = (request.POST.get("unidade") or "")[:40]
        item.valor_unitario = unitario
        item.valor_previsto = total
        item.classificacao_orcamentaria = (request.POST.get("classificacao_orcamentaria") or "")[:160]
        item.tipo_despesa = (request.POST.get("tipo_despesa") or "")[:80]
        item.recurso = (request.POST.get("recurso") or "")[:80]
        item.categoria = item.classificacao_orcamentaria[:120]
        item.natureza = natureza
        self._marcar(item, request.user, StatusRevisaoPlano.CORRIGIDO)
        item.save()
        self._auditar(request, prestacao, plano, "corrigir_item", item=item)
        messages.success(request, "Item corrigido. A descrição original e os outros itens foram preservados.")

    def _item(self, plano, identificador):
        try:
            return plano.itens.get(pk=int(identificador))
        except (TypeError, ValueError, ItemPlanoTrabalho.DoesNotExist):
            return None

    def _meta(self, plano, identificador):
        try:
            return plano.metas.get(pk=int(identificador))
        except (TypeError, ValueError, Meta.DoesNotExist):
            return None

    def _marcar(self, registro, usuario, status):
        registro.status_revisao = status
        registro.revisado_por = usuario
        registro.revisado_em = timezone.now()

    def _auditar(self, request, prestacao, plano, acao, item=None, meta=None):
        registrar_evento(
            evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
            descricao="Revisão humana do plano de trabalho",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path[:255],
            detalhes={
                "prestacao": prestacao.pk,
                "documento": plano.documento_id,
                "plano": plano.pk,
                "acao": acao,
                "item": item.pk if item else None,
                "meta": meta.pk if meta else None,
            },
        )


def _dinheiro_post(valor, obrigatorio=False) -> tuple[Decimal | None, bool]:
    bruto = (valor or "").strip()
    if not bruto:
        return None, not obrigatorio
    numero = dinheiro(bruto)
    if numero is None or numero < 0:
        return None, False
    return numero, True


def _data_iso(valor):
    from datetime import date

    bruto = (valor or "").strip()
    if not bruto:
        return None
    try:
        return date.fromisoformat(bruto)
    except ValueError:
        return None
