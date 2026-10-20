from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.laboratorio.catalogo import CATALOGO_TIPOS, rotulo_tipo
from aplicacao.laboratorio.escolhas import (
    EstadoCampo,
    EstadoClassificacao,
    EstadoRevisao,
    StatusPendencia,
)
from aplicacao.laboratorio.forms import (
    FormularioCampo,
    FormularioClassificacaoRegiao,
    FormularioIlegibilidade,
    FormularioPendencia,
    FormularioReprocessamento,
    FormularioVinculo,
)
from aplicacao.laboratorio.models import (
    CampoExtraido,
    InventarioPagina,
    LoteLaboratorio,
    PendenciaDocumental,
    RegiaoDocumental,
    RevisaoLaboratorio,
    VinculoEvidencia,
)
from aplicacao.laboratorio.servico import montar_relatorio, processar_lote
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import PERFIS_OPERACIONAIS, PerfilExigidoMixin, exigir_atuar_na_prestacao, exigir_ver_prestacao


def _lote_visivel(request, lote_pk: int) -> LoteLaboratorio:
    lote = get_object_or_404(
        LoteLaboratorio.objects.select_related("prestacao_parceria", "documento"),
        pk=lote_pk,
    )
    exigir_ver_prestacao(request.user, lote.prestacao_parceria)
    return lote


def _registrar_revisao(lote, usuario, alvo, alvo_id, acao, justificativa="", detalhe=None):
    RevisaoLaboratorio.objects.create(
        lote=lote,
        alvo=alvo,
        alvo_id=alvo_id,
        acao=acao,
        justificativa=justificativa or "",
        detalhe=detalhe or {},
        responsavel=usuario,
    )
    registrar_evento(
        evento=RegistroAuditoria.Evento.REVISAO_HUMANA,
        descricao=f"Revisão do laboratório: {acao}",
        usuario=usuario,
        detalhes={"lote": lote.pk, "alvo": alvo, "alvo_id": alvo_id, "acao": acao},
    )


class LaboratorioProcessoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        exigir_ver_prestacao(request.user, prestacao)
        lotes = (
            LoteLaboratorio.objects.filter(prestacao_parceria=prestacao)
            .select_related("documento")
            .order_by("-importado_em")
        )
        return render(
            request,
            "laboratorio/processo.html",
            {
                "prestacao": prestacao,
                "lotes": lotes,
                "catalogo": CATALOGO_TIPOS,
            },
        )


class LaboratorioLoteView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        relatorio = montar_relatorio(lote)
        paginas = lote.paginas.all()
        return render(
            request,
            "laboratorio/lote.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "paginas": paginas,
                "relatorio": relatorio,
                "catalogo": CATALOGO_TIPOS,
                "rotulo_tipo": rotulo_tipo,
            },
        )


class LaboratorioCuradoriaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        numero = int(request.GET.get("pagina") or 1)
        pagina = lote.paginas.filter(numero_fisico=numero).first()
        if pagina is None:
            pagina = lote.paginas.order_by("numero_fisico").first()
        regioes = []
        if pagina:
            regioes = list(pagina.regioes.prefetch_related("campos").order_by("ordem", "id"))
        vinculos = VinculoEvidencia.objects.filter(lote=lote).select_related("origem", "destino", "origem__pagina", "destino__pagina")[:50]
        pendencias = lote.pendencias.select_related("pagina", "regiao").order_by("-criado_em")[:30]
        revisoes = lote.revisoes.select_related("responsavel").order_by("-criado_em")[:20]
        return render(
            request,
            "laboratorio/curadoria.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "pagina": pagina,
                "regioes": regioes,
                "vinculos": vinculos,
                "pendencias": pendencias,
                "revisoes": revisoes,
                "form_classificacao": FormularioClassificacaoRegiao(),
                "form_campo": FormularioCampo(),
                "form_vinculo": FormularioVinculo(),
                "form_pendencia": FormularioPendencia(),
                "form_ilegivel": FormularioIlegibilidade(),
                "form_reprocessar": FormularioReprocessamento(),
                "arquivo_url": reverse("documentos:arquivo", kwargs={"pk": lote.documento_id}),
                "rotulo_tipo": rotulo_tipo,
                "total_paginas": lote.quantidade_paginas,
            },
        )


class RevisarRegiaoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, regiao_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        regiao = get_object_or_404(RegiaoDocumental, pk=regiao_pk, lote=lote)
        form = FormularioClassificacaoRegiao(request.POST)
        if not form.is_valid():
            messages.error(request, "Não foi possível registrar a classificação.")
            return redirect(_curadoria_url(lote, regiao.pagina.numero_fisico))
        anterior = regiao.tipo_documental
        novo = form.cleaned_data["tipo_documental"]
        regiao.tipo_documental = novo
        if form.cleaned_data.get("x") is not None:
            regiao.x = form.cleaned_data["x"]
        if form.cleaned_data.get("y") is not None:
            regiao.y = form.cleaned_data["y"]
        if form.cleaned_data.get("largura") is not None:
            regiao.largura = form.cleaned_data["largura"]
        if form.cleaned_data.get("altura") is not None:
            regiao.altura = form.cleaned_data["altura"]
        regiao.estado_classificacao = (
            EstadoClassificacao.CORRIGIDO if anterior != novo else EstadoClassificacao.CONFIRMADO
        )
        regiao.estado_revisao = EstadoRevisao.REVISADA
        regiao.justificativa = form.cleaned_data.get("justificativa") or ""
        regiao.revisado_por = request.user
        regiao.revisado_em = timezone.now()
        regiao.versao_classificacao += 1
        regiao.save()
        pagina = regiao.pagina
        pagina.estado_classificacao = regiao.estado_classificacao
        pagina.estado_revisao = EstadoRevisao.REVISADA
        pagina.save(update_fields=["estado_classificacao", "estado_revisao"])
        _registrar_revisao(
            lote,
            request.user,
            "regiao",
            regiao.pk,
            "classificacao_confirmada" if anterior == novo else "classificacao_corrigida",
            regiao.justificativa,
            {"anterior": anterior, "novo": novo},
        )
        messages.success(request, "Classificação registrada. Isso não aprova a prestação de contas.")
        return redirect(_curadoria_url(lote, pagina.numero_fisico))


class RevisarCampoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, campo_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        campo = get_object_or_404(CampoExtraido.objects.select_related("regiao__pagina"), pk=campo_pk, regiao__lote=lote)
        form = FormularioCampo(request.POST)
        if not form.is_valid():
            messages.error(request, "Não foi possível registrar a revisão do campo.")
            return redirect(_curadoria_url(lote, campo.numero_pagina))
        historico = list(campo.historico_correcoes or [])
        historico.append(
            {
                "em": timezone.now().isoformat(),
                "usuario": request.user.username,
                "acao": form.cleaned_data["acao"],
                "antes": campo.valor_original,
                "depois": form.cleaned_data.get("valor_original") or "",
                "justificativa": form.cleaned_data.get("justificativa") or "",
            }
        )
        acao = form.cleaned_data["acao"]
        if acao == "confirmar":
            campo.estado_revisao = EstadoCampo.CONFIRMADO
        elif acao == "corrigir":
            campo.valor_original = form.cleaned_data.get("valor_original") or ""
            campo.valor_normalizado = campo.valor_original
            campo.estado_revisao = EstadoCampo.CORRIGIDO
        else:
            campo.valor_original = ""
            campo.valor_normalizado = ""
            campo.estado_revisao = EstadoCampo.AUSENTE
        campo.historico_correcoes = historico
        campo.revisado_por = request.user
        campo.revisado_em = timezone.now()
        campo.save()
        _registrar_revisao(
            lote,
            request.user,
            "campo",
            campo.pk,
            f"extracao_{acao}",
            form.cleaned_data.get("justificativa") or "",
        )
        messages.success(request, "Extração revisada. Isso não analisa nem aprova despesa.")
        return redirect(_curadoria_url(lote, campo.numero_pagina))


class RevisarVinculoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, vinculo_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        vinculo = get_object_or_404(VinculoEvidencia, pk=vinculo_pk, lote=lote)
        form = FormularioVinculo(request.POST)
        if not form.is_valid():
            messages.error(request, "Não foi possível atualizar o vínculo.")
            return redirect(_curadoria_url(lote, vinculo.origem.pagina.numero_fisico))
        vinculo.estado = form.cleaned_data["estado"]
        vinculo.justificativa = form.cleaned_data.get("justificativa") or ""
        vinculo.revisado_por = request.user
        vinculo.revisado_em = timezone.now()
        vinculo.save()
        _registrar_revisao(
            lote,
            request.user,
            "vinculo",
            vinculo.pk,
            "vinculo_" + vinculo.estado,
            vinculo.justificativa,
        )
        messages.success(request, "Vínculo atualizado. Coincidência de valores permanece só um critério.")
        return redirect(_curadoria_url(lote, vinculo.origem.pagina.numero_fisico))


class CriarPendenciaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        form = FormularioPendencia(request.POST)
        numero = int(request.POST.get("pagina") or 1)
        pagina = lote.paginas.filter(numero_fisico=numero).first()
        if not form.is_valid():
            messages.error(request, "Não foi possível abrir a pendência.")
            return redirect(_curadoria_url(lote, numero))
        pendencia = PendenciaDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            motivo=form.cleaned_data["motivo"],
            prioridade=form.cleaned_data["prioridade"],
            status=form.cleaned_data["status"],
            solicitacao_esclarecimento=form.cleaned_data.get("solicitacao_esclarecimento") or "",
            responsavel=request.user,
            historico=[{"evento": "abertura", "em": timezone.now().isoformat(), "usuario": request.user.username}],
        )
        _registrar_revisao(lote, request.user, "pendencia", pendencia.pk, "pendencia_aberta", pendencia.motivo)
        messages.success(request, "Pendência registrada. Nenhuma diligência externa foi disparada.")
        return redirect(_curadoria_url(lote, numero))


class MarcarIlegivelView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, pagina_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        pagina = get_object_or_404(InventarioPagina, pk=pagina_pk, lote=lote)
        form = FormularioIlegibilidade(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe a justificativa da ilegibilidade.")
            return redirect(_curadoria_url(lote, pagina.numero_fisico))
        pagina.estado_revisao = EstadoRevisao.ILEGIVEL
        pagina.legibilidade = "ilegivel"
        pagina.save(update_fields=["estado_revisao", "legibilidade"])
        PendenciaDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            motivo="Página marcada como ilegível na curadoria.",
            status=StatusPendencia.ABERTA,
            responsavel=request.user,
            historico=[{"evento": "ilegivel", "em": timezone.now().isoformat(), "justificativa": form.cleaned_data["justificativa"]}],
        )
        _registrar_revisao(lote, request.user, "pagina", pagina.pk, "ilegivel", form.cleaned_data["justificativa"])
        messages.success(request, "Ilegibilidade registrada.")
        return redirect(_curadoria_url(lote, pagina.numero_fisico))


class SolicitarReprocessamentoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        form = FormularioReprocessamento(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe o motivo do reprocessamento.")
            return redirect(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}))
        _registrar_revisao(lote, request.user, "lote", lote.pk, "reprocessamento_solicitado", form.cleaned_data["motivo"])
        processar_lote(lote.pk, usuario=request.user)
        messages.success(request, "Reprocessamento local concluído. O PDF original permanece imutável.")
        return redirect(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}))


class RelatorioLaboratorioView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        return render(
            request,
            "laboratorio/relatorio.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "relatorio": montar_relatorio(lote),
                "rotulo_tipo": rotulo_tipo,
            },
        )


def _curadoria_url(lote, numero_pagina: int) -> str:
    return reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}) + f"?pagina={numero_pagina}"
