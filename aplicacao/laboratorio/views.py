from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao
from aplicacao.laboratorio.apresentacao import (
    campos_conferencia,
    comparar_pagina,
    filtrar_paginas,
    nivel_de_rastreio,
    resumo_pagina,
    resumo_peca,
    secoes_da_peca,
)
from django.db.models import Q

from aplicacao.laboratorio.catalogo import CATALOGO_TIPOS, escolhas_tipo
from aplicacao.laboratorio.escolhas import (
    EstadoCampo,
    EstadoClassificacao,
    EstadoRevisao,
    StatusPendencia,
)
from aplicacao.laboratorio.forms import (
    FormularioCampo,
    FormularioClassificacaoRegiao,
    FormularioRubrica,
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
    RubricaExtraida,
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


def _url_do_pdf(lote) -> str:
    """A versão na URL invalida o cache do navegador quando o arquivo muda."""
    url = reverse("documentos:arquivo", kwargs={"pk": lote.documento_id})
    identidade = lote.documento.hash_sha256
    if identidade:
        return f"{url}?v={identidade}"
    return url


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


def _curadoria_url(lote, numero_pagina: int, peca: int | None = None) -> str:
    url = reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}) + f"?pagina={numero_pagina}"
    if peca:
        url += f"&peca={peca}"
    return url


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
        itens = [{"lote": lote, "relatorio": montar_relatorio(lote)} for lote in lotes]
        return render(
            request,
            "laboratorio/processo.html",
            {
                "prestacao": prestacao,
                "itens": itens,
                "catalogo": CATALOGO_TIPOS,
            },
        )


class LaboratorioLoteView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        relatorio = montar_relatorio(lote)
        paginas = filtrar_paginas(lote, request.GET)
        from aplicacao.laboratorio.models import RevisaoLaboratorio

        inspecionadas = set(
            RevisaoLaboratorio.objects.filter(lote=lote, alvo="descoberta_pagina", acao="inspecao_ocr").values_list(
                "alvo_id", flat=True
            )
        )
        peca_busca = (request.GET.get("peca") or "").strip()
        peca_busca_id = int(peca_busca) if peca_busca.isdigit() else None
        linhas = [
            {
                "pagina": pagina,
                "resumo": resumo_pagina(pagina),
                "pecas": list(pagina.regioes.all()),
                "inspecao": pagina.numero_fisico in inspecionadas,
                "peca_busca": peca_busca_id,
            }
            for pagina in paginas
        ]
        return render(
            request,
            "laboratorio/lote.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "linhas": linhas,
                "relatorio": relatorio,
                "catalogo": CATALOGO_TIPOS,
                "filtros": {
                    "peca": request.GET.get("peca", ""),
                    "pagina": request.GET.get("pagina", ""),
                    "tipo": request.GET.get("tipo", ""),
                    "classificacao": request.GET.get("classificacao", ""),
                    "qualidade": request.GET.get("qualidade", ""),
                    "tecnica": request.GET.get("tecnica", ""),
                    "revisao": request.GET.get("revisao", ""),
                    "inspecao": request.GET.get("inspecao", ""),
                },
                "tipos_filtro": escolhas_tipo(),
                "qualidades": QualidadeExtracao.choices,
                "tecnicas": MetodoExtracao.choices,
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
            regioes = [
                r
                for r in pagina.regioes.prefetch_related("campos", "rubricas").order_by("ordem", "id")
                if r.tipo_documental != "outros_nao_classificados"
            ]
        peca_id = request.GET.get("peca")
        peca_selecionada = None
        if peca_id and str(peca_id).isdigit() and pagina is not None:
            pedida = pagina.regioes.prefetch_related("campos", "rubricas").filter(pk=int(peca_id)).first()
            if pedida is not None and pedida not in regioes:
                regioes.append(pedida)
            peca_selecionada = next((r for r in regioes if r.pk == int(peca_id)), None)
        if peca_selecionada is None and regioes:
            peca_selecionada = regioes[0]
        for regiao in regioes:
            regiao.resumo = resumo_peca(regiao)
        campos = campos_conferencia(peca_selecionada) if peca_selecionada else []
        rubricas = list(peca_selecionada.rubricas.all()) if peca_selecionada else []
        pagina_peca = pagina.numero_fisico if pagina is not None else None
        for campo in campos:
            campo.nivel_rastreio = nivel_de_rastreio(campo, pagina_peca=pagina_peca)
        for rubrica in rubricas:
            rubrica.nivel_rastreio = nivel_de_rastreio(rubrica, pagina_peca=pagina_peca)
        secoes = (
            secoes_da_peca(peca_selecionada.tipo_documental, campos, rubricas_estruturadas=bool(rubricas))
            if peca_selecionada
            else []
        )
        pendentes_rubrica = sum(1 for rubrica in rubricas if rubrica.estado_revisao == "pendente")
        vinculos = []
        pendencias_peca = []
        if peca_selecionada:
            vinculos = (
                VinculoEvidencia.objects.filter(lote=lote)
                .filter(Q(origem=peca_selecionada) | Q(destino=peca_selecionada))
                .select_related("origem", "destino", "origem__pagina", "destino__pagina")[:20]
            )
            pendencias_peca = list(
                PendenciaDocumental.objects.filter(lote=lote, regiao=peca_selecionada).order_by("-criado_em")[:10]
            )
        return render(
            request,
            "laboratorio/curadoria.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "pagina": pagina,
                "regioes": regioes,
                "peca": peca_selecionada,
                "campos": campos,
                "secoes": secoes,
                "rubricas": rubricas,
                "pendentes_rubrica": pendentes_rubrica,
                "comparacao": comparar_pagina(regioes),
                "vinculos": vinculos,
                "pendencias": pendencias_peca,
                "revisoes": lote.revisoes.select_related("responsavel").order_by("-criado_em")[:20],
                "form_classificacao": FormularioClassificacaoRegiao(),
                "form_campo": FormularioCampo(),
                "form_vinculo": FormularioVinculo(),
                "form_pendencia": FormularioPendencia(),
                "form_ilegivel": FormularioIlegibilidade(),
                "form_reprocessar": FormularioReprocessamento(),
                "arquivo_url": _url_do_pdf(lote),
                "total_paginas": lote.quantidade_paginas,
                "resumo_pagina": resumo_pagina(pagina) if pagina else "",
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
            return redirect(_curadoria_url(lote, regiao.pagina.numero_fisico, regiao.pk))
        anterior = regiao.tipo_documental
        novo = form.cleaned_data["tipo_documental"]
        if anterior != novo and not (form.cleaned_data.get("justificativa") or "").strip():
            messages.error(request, "Corrigir a classificação exige justificativa.")
            return redirect(_curadoria_url(lote, regiao.pagina.numero_fisico, regiao.pk))
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
        return redirect(_curadoria_url(lote, pagina.numero_fisico, regiao.pk))


class AjustarRegiaoView(PerfilExigidoMixin, View):
    """Grava o retângulo arrastado sem confirmar a classificação nem a extração."""

    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, regiao_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        regiao = get_object_or_404(RegiaoDocumental, pk=regiao_pk, lote=lote)
        try:
            x = float(request.POST.get("x", ""))
            y = float(request.POST.get("y", ""))
            largura = float(request.POST.get("largura", ""))
            altura = float(request.POST.get("altura", ""))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "erro": "Coordenadas inválidas."}, status=400)
        if min(x, y, largura, altura) < 0 or largura < 0.02 or altura < 0.02 or x + largura > 1.02 or y + altura > 1.02:
            return JsonResponse({"ok": False, "erro": "A região ficou fora da página."}, status=400)
        regiao.x = round(min(x, 1), 4)
        regiao.y = round(min(y, 1), 4)
        regiao.largura = round(min(largura, 1), 4)
        regiao.altura = round(min(altura, 1), 4)
        regiao.metodo_deteccao = "ajuste_humano"
        regiao.versao_classificacao += 1
        regiao.justificativa = "Ajuste visual da região pelo auditor."
        regiao.save(update_fields=["x", "y", "largura", "altura", "metodo_deteccao", "versao_classificacao", "justificativa", "atualizado_em"])
        _registrar_revisao(
            lote,
            request.user,
            "regiao",
            regiao.pk,
            "ajuste_visual",
            regiao.justificativa,
            {"x": regiao.x, "y": regiao.y, "largura": regiao.largura, "altura": regiao.altura},
        )
        return JsonResponse({"ok": True, "revisao": "pendente"})


class RevisarCampoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, campo_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        campo = get_object_or_404(CampoExtraido.objects.select_related("regiao__pagina"), pk=campo_pk, regiao__lote=lote)
        form = FormularioCampo(request.POST)
        if not form.is_valid():
            messages.error(request, "Não foi possível registrar a revisão do campo.")
            return redirect(_curadoria_url(lote, campo.numero_pagina, campo.regiao_id))
        acao = form.cleaned_data["acao"]
        justificativa = (form.cleaned_data.get("justificativa") or "").strip()
        novo_valor = form.cleaned_data.get("valor_original") or ""
        if acao == "confirmar" and novo_valor.strip() != (campo.valor_original or "").strip():
            messages.error(request, "Para alterar o valor, use Corrigir e registre a justificativa.")
            return redirect(_curadoria_url(lote, campo.numero_pagina, campo.regiao_id))
        if acao in {"corrigir", "ausente", "nao_localizado", "ilegivel"} and not justificativa:
            messages.error(request, "Correção, rejeição ou mudança de estado exige justificativa.")
            return redirect(_curadoria_url(lote, campo.numero_pagina, campo.regiao_id))
        historico = list(campo.historico_correcoes or [])
        historico.append(
            {
                "em": timezone.now().isoformat(),
                "usuario": request.user.username,
                "acao": acao,
                "antes": campo.valor_original,
                "depois": novo_valor if acao == "corrigir" else campo.valor_original,
                "justificativa": justificativa,
            }
        )
        if acao == "confirmar":
            campo.estado_revisao = EstadoCampo.CONFIRMADO
        elif acao == "corrigir":
            from aplicacao.laboratorio.extracao import CHAVES_MOEDA, _moeda_para_decimal

            campo.valor_original = novo_valor
            decimal = _moeda_para_decimal(novo_valor) if campo.chave in CHAVES_MOEDA else None
            campo.valor_normalizado = str(decimal) if decimal is not None else novo_valor
            campo.estado_revisao = EstadoCampo.CORRIGIDO
        elif acao == "ilegivel":
            campo.estado_revisao = EstadoCampo.ILEGIVEL
            campo.estado_confianca = "ilegivel"
        elif acao == "pendente":
            campo.estado_revisao = EstadoCampo.PENDENTE
        else:
            campo.estado_revisao = EstadoCampo.AUSENTE
            campo.estado_confianca = "nao_localizado"
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
        return redirect(_curadoria_url(lote, campo.numero_pagina, campo.regiao_id))


class RevisarRubricaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, rubrica_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        rubrica = get_object_or_404(
            RubricaExtraida.objects.select_related("regiao__pagina"),
            pk=rubrica_pk,
            regiao__lote=lote,
        )
        form = FormularioRubrica(request.POST)
        if not form.is_valid():
            messages.error(request, "Não foi possível registrar a revisão da rubrica.")
            return redirect(_curadoria_url(lote, rubrica.regiao.pagina.numero_fisico, rubrica.regiao_id))
        acao = form.cleaned_data["acao"]
        justificativa = (form.cleaned_data.get("justificativa") or "").strip()
        if acao == "confirmar" and (
            form.cleaned_data["valor_original"].strip() != rubrica.valor_original
            or form.cleaned_data["descricao"].strip() != rubrica.descricao
            or form.cleaned_data["referencia"].strip() != rubrica.referencia
        ):
            messages.error(request, "Para alterar a rubrica, use Corrigir e registre a justificativa.")
            return redirect(_curadoria_url(lote, rubrica.regiao.pagina.numero_fisico, rubrica.regiao_id))
        if acao in {"corrigir", "nao_localizado", "ilegivel"} and not justificativa:
            messages.error(request, "Correção ou rejeição da rubrica exige justificativa.")
            return redirect(_curadoria_url(lote, rubrica.regiao.pagina.numero_fisico, rubrica.regiao_id))
        historico = list(rubrica.historico_correcoes or [])
        historico.append(
            {
                "em": timezone.now().isoformat(),
                "usuario": request.user.username,
                "acao": acao,
                "antes": rubrica.valor_original,
                "justificativa": justificativa,
            }
        )
        if acao == "corrigir":
            from aplicacao.laboratorio.extracao import _moeda_para_decimal

            rubrica.descricao = form.cleaned_data["descricao"].strip()
            rubrica.referencia = form.cleaned_data["referencia"].strip()
            rubrica.valor_original = form.cleaned_data["valor_original"].strip()
            decimal = _moeda_para_decimal(rubrica.valor_original)
            rubrica.valor_normalizado = str(decimal) if decimal is not None else rubrica.valor_original
            rubrica.estado_revisao = EstadoCampo.CORRIGIDO
        elif acao == "confirmar":
            rubrica.estado_revisao = EstadoCampo.CONFIRMADO
        elif acao == "ilegivel":
            rubrica.estado_revisao = EstadoCampo.ILEGIVEL
        elif acao == "pendente":
            rubrica.estado_revisao = EstadoCampo.PENDENTE
        else:
            rubrica.estado_revisao = EstadoCampo.AUSENTE
        rubrica.historico_correcoes = historico
        rubrica.revisado_por = request.user
        rubrica.revisado_em = timezone.now()
        rubrica.save()
        _registrar_revisao(lote, request.user, "rubrica", rubrica.pk, f"rubrica_{acao}", justificativa)
        messages.success(request, "Rubrica revisada individualmente. Isso não confirma as demais nem aprova despesa.")
        return redirect(_curadoria_url(lote, rubrica.regiao.pagina.numero_fisico, rubrica.regiao_id))


class RevisarVinculoView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, vinculo_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        vinculo = get_object_or_404(VinculoEvidencia, pk=vinculo_pk, lote=lote)
        form = FormularioVinculo(request.POST)
        if not form.is_valid():
            messages.error(request, "Não foi possível atualizar o vínculo.")
            return redirect(_curadoria_url(lote, vinculo.origem.pagina.numero_fisico, vinculo.origem_id))
        if form.cleaned_data["estado"] != vinculo.estado and not (form.cleaned_data.get("justificativa") or "").strip():
            messages.error(request, "Alterar o vínculo exige justificativa.")
            return redirect(_curadoria_url(lote, vinculo.origem.pagina.numero_fisico, vinculo.origem_id))
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
        return redirect(_curadoria_url(lote, vinculo.origem.pagina.numero_fisico, vinculo.origem_id))


class CriarPendenciaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk):
        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        form = FormularioPendencia(request.POST)
        numero = int(request.POST.get("pagina") or 1)
        peca_id = request.POST.get("peca")
        pagina = lote.paginas.filter(numero_fisico=numero).first()
        regiao = None
        if peca_id and str(peca_id).isdigit():
            regiao = RegiaoDocumental.objects.filter(pk=int(peca_id), lote=lote).first()
        if not form.is_valid():
            messages.error(request, "Não foi possível abrir a pendência.")
            return redirect(_curadoria_url(lote, numero, int(peca_id) if peca_id and str(peca_id).isdigit() else None))
        pendencia = PendenciaDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            regiao=regiao,
            motivo=form.cleaned_data["motivo"],
            prioridade=form.cleaned_data["prioridade"],
            status=form.cleaned_data["status"],
            solicitacao_esclarecimento=form.cleaned_data.get("solicitacao_esclarecimento") or "",
            responsavel=request.user,
            historico=[{"evento": "abertura", "em": timezone.now().isoformat(), "usuario": request.user.username}],
        )
        _registrar_revisao(lote, request.user, "pendencia", pendencia.pk, "pendencia_aberta", pendencia.motivo)
        messages.success(request, "Pendência registrada. Nenhuma diligência externa foi disparada.")
        return redirect(_curadoria_url(lote, numero, regiao.pk if regiao else None))


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
        paginas_ocr = set()
        raw = (request.POST.get("ocr_paginas") or "").strip()
        if raw:
            paginas_ocr = {int(item.strip()) for item in raw.split(",") if item.strip().isdigit()}
        _registrar_revisao(lote, request.user, "lote", lote.pk, "reprocessamento_solicitado", form.cleaned_data["motivo"])
        processar_lote(lote.pk, usuario=request.user, paginas_ocr=paginas_ocr or None)
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
            },
        )


class ConciliacaoFinanceiraView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, lote_pk):
        from aplicacao.laboratorio.apresentacao import ficha_cadeia
        from aplicacao.laboratorio.catalogo import rotulo_tipo
        from aplicacao.laboratorio.conciliacao import painel_da_cadeia
        from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada

        lote = _lote_visivel(request, lote_pk)
        cadeias = list(
            lote.cadeias.select_related(
                "item_plano",
                "execucao__pagina",
                "comprovante__pagina",
                "apoio__pagina",
                "revisado_por",
            ).prefetch_related("execucao__campos", "comprovante__campos", "apoio__campos")
        )
        for cadeia in cadeias:
            cadeia.painel = painel_da_cadeia(cadeia)
            cadeia.ficha = ficha_cadeia(cadeia)
        return render(
            request,
            "laboratorio/conciliacao.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "cadeias": cadeias,
                "painel": montar_conferencia_integrada(lote),
                "rotulo_tipo": rotulo_tipo,
                "rotulos_separacao": {
                    "vinculo": "Vínculo",
                    "consistencia_matematica": "Consistência matemática",
                    "comprovacao_documental": "Comprovação documental",
                    "analise_conformidade": "Análise de conformidade",
                    "decisao_administrativa": "Decisão administrativa",
                },
                "rotulos_situacao": {
                    "confere": "Confere",
                    "diverge": "Diverge",
                    "nao_verificavel": "Não verificável",
                    "pendente": "Pendente de revisão humana",
                    "sugerido": "Sugerido",
                    "nao_aplicavel": "Não aplicável",
                },
            },
        )


class ConferenciaIntegradaView(PerfilExigidoMixin, View):
    """Consulta agregada. Abrir a tela não cria nem atualiza cadeias."""

    perfis_permitidos = PERFIS_OPERACIONAIS

    def get(self, request, lote_pk):
        from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
        from aplicacao.laboratorio.descoberta import ler_descobertas

        lote = _lote_visivel(request, lote_pk)
        return render(
            request,
            "laboratorio/conferencia_integrada.html",
            {
                "prestacao": lote.prestacao_parceria,
                "lote": lote,
                "painel": montar_conferencia_integrada(lote),
                "descobertas": ler_descobertas(lote),
            },
        )


class RevisarCadeiaView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIS_OPERACIONAIS

    def post(self, request, lote_pk, cadeia_pk):
        from aplicacao.laboratorio.escolhas import EstadoVinculo
        from aplicacao.laboratorio.models import CadeiaConciliacao

        lote = _lote_visivel(request, lote_pk)
        exigir_atuar_na_prestacao(request.user, lote.prestacao_parceria)
        cadeia = get_object_or_404(CadeiaConciliacao, pk=cadeia_pk, lote=lote)
        acao = (request.POST.get("acao") or "").strip()
        justificativa = (request.POST.get("justificativa") or "").strip()
        if acao == "rejeitar" and not justificativa:
            messages.error(request, "Rejeitar o vínculo exige justificativa.")
            return redirect(reverse("laboratorio:conciliacao", kwargs={"lote_pk": lote.pk}))
        if acao == "confirmar":
            cadeia.estado = EstadoVinculo.CONFIRMADO
        elif acao == "rejeitar":
            cadeia.estado = EstadoVinculo.REJEITADO
        elif acao == "pendente":
            cadeia.estado = EstadoVinculo.SUGERIDO
        else:
            messages.error(request, "Ação de revisão não reconhecida.")
            return redirect(reverse("laboratorio:conciliacao", kwargs={"lote_pk": lote.pk}))
        cadeia.justificativa = justificativa
        cadeia.revisado_por = request.user
        cadeia.revisado_em = timezone.now()
        cadeia.save(update_fields=["estado", "justificativa", "revisado_por", "revisado_em"])
        _registrar_revisao(
            lote,
            request.user,
            "cadeia",
            cadeia.pk,
            acao,
            justificativa,
            {"codigo": cadeia.codigo},
        )
        messages.success(request, "Revisão do vínculo registrada. Nenhuma despesa foi aprovada.")
        return redirect(reverse("laboratorio:conciliacao", kwargs={"lote_pk": lote.pk}))
