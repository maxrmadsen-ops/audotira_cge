"""Conferência sequencial das despesas previstas e etapas ainda não implementadas."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from aplicacao.prestacoes_contas.escolhas import NaturezaItem
from aplicacao.prestacoes_contas.models import PlanoTrabalho, PrestacaoContas
from aplicacao.prestacoes_contas.situacao_revisao import chaves_ratificacao, rotulo_revisao
from aplicacao.usuarios.acesso import exigir_ver_prestacao, pode_atuar_na_prestacao

ETAPAS_FUTURAS = {
    "prestacoes-parciais": {
        "titulo": "Prestações de Contas Parciais",
        "texto": "Esta etapa ainda não recebe prestações parciais. O envio e a classificação dos PDFs continuam na tela Documentos, que não é a prestação parcial.",
        "aba": "documentos",
        "destino": "Documentos",
    },
    "prestacao-final": {
        "titulo": "Prestação de Contas Final",
        "texto": "Esta etapa ainda não conclui a prestação de contas. A execução atual das regras continua na tela Verificações e não aprova a prestação.",
        "aba": "analise",
        "destino": "Verificações",
    },
    "regras-validacao": {
        "titulo": "Regras e Validação",
        "texto": "Esta etapa ainda não reúne regras e validação num fluxo próprio. O catálogo e os achados atuais continuam nas telas Verificações e Achados.",
        "aba": "achados",
        "destino": "Achados",
    },
}


class EtapaFuturaView(LoginRequiredMixin, View):
    def get(self, request, pk, slug):
        etapa = ETAPAS_FUTURAS.get(slug)
        if etapa is None:
            raise Http404("Etapa não disponível.")
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        exigir_ver_prestacao(request.user, prestacao)
        return render(
            request,
            "prestacoes_contas/etapa_futura.html",
            {
                "prestacao": prestacao,
                "etapa": etapa,
                "url_atual": reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}) + f"?aba={etapa['aba']}",
            },
        )


class ConferenciaDespesasView(LoginRequiredMixin, View):
    def get(self, request, pk, plano_pk):
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        exigir_ver_prestacao(request.user, prestacao)
        plano = get_object_or_404(PlanoTrabalho.objects.prefetch_related("itens"), pk=plano_pk, prestacao=prestacao)
        itens = list(plano.itens.order_by("ordem", "pk"))
        item = _item_atual(itens, request.GET.get("item"))
        indice = itens.index(item) + 1 if item is not None else 0
        chaves = chaves_ratificacao(prestacao)
        filtros = _filtros(request)
        return render(
            request,
            "prestacoes_contas/conferencia.html",
            {
                "prestacao": prestacao,
                "plano": plano,
                "item": item,
                "indice": indice,
                "total": len(itens),
                "anterior_url": _url_item(prestacao, plano, itens[indice - 2], filtros) if item and indice > 1 else "",
                "proximo_url": _url_item(prestacao, plano, itens[indice], filtros) if item and indice < len(itens) else "",
                "lista_url": _url_lista(prestacao, plano, filtros),
                "rotulo": rotulo_revisao(item, "item", chaves) if item else "",
                "pode_alterar": pode_atuar_na_prestacao(request.user, prestacao),
                "url_revisao": reverse("prestacoes_contas:revisao_plano", kwargs={"pk": prestacao.pk, "plano_pk": plano.pk}),
                "naturezas": NaturezaItem.choices,
                "pagina_pdf": item.pagina if item and item.pagina else 1,
                "mostrar_pdf": bool(plano.documento_id and item and item.pagina),
                "filtros": filtros,
            },
        )


def _item_atual(itens, pedido):
    if not itens:
        return None
    if pedido and str(pedido).isdigit():
        escolhido = next((item for item in itens if item.pk == int(pedido)), None)
        if escolhido is not None:
            return escolhido
    return itens[0]


def _url_item(prestacao, plano, item, filtros) -> str:
    from urllib.parse import urlencode

    base = reverse("prestacoes_contas:conferencia_despesas", kwargs={"pk": prestacao.pk, "plano_pk": plano.pk})
    consulta = {"item": item.pk}
    consulta.update({nome: valor for nome, valor in filtros.items() if valor})
    return base + "?" + urlencode(consulta)


def _filtros(request) -> dict[str, str]:
    return {nome: (request.GET.get(nome) or "").strip() for nome in ("q", "estado", "natureza", "ordem")}


def _url_lista(prestacao, plano, filtros) -> str:
    from urllib.parse import urlencode

    consulta = {"aba": "plano", "plano": plano.pk, "secao": "despesas"}
    consulta.update({nome: valor for nome, valor in filtros.items() if valor})
    return reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}) + "?" + urlencode(consulta)
