"""Fila de trabalho. Ausência de evidência não vira irregularidade."""

from django.urls import reverse

from aplicacao.documentos.models import Documento
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, Meta, PlanoTrabalho
from aplicacao.prestacoes_contas.situacao_revisao import chaves_ratificacao, rotulo_revisao
from aplicacao.usuarios.acesso import prestacoes_visiveis


def listar_pendencias(usuario, tipo: str = "") -> list[dict]:
    prestacoes = prestacoes_visiveis(usuario)
    linhas = []
    if tipo in {"", "plano"}:
        for plano in PlanoTrabalho.objects.filter(prestacao__in=prestacoes, status_revisao=StatusRevisaoPlano.AGUARDANDO).select_related("prestacao"):
            linhas.append(_linha(plano.prestacao, "Preparação", "Identificação do plano", plano.titulo, "Aguardando revisão", plano.prestacao.analista_responsavel, _url_plano(plano)))
        for item in ItemPlanoTrabalho.objects.filter(plano__prestacao__in=prestacoes, status_revisao=StatusRevisaoPlano.AGUARDANDO).select_related("plano__prestacao", "plano__prestacao__analista_responsavel"):
            chaves = chaves_ratificacao(item.plano.prestacao)
            situacao = rotulo_revisao(item, "item", chaves)
            linhas.append(_linha(item.plano.prestacao, "Preparação", "Item do plano", item.descricao[:120], situacao, item.plano.prestacao.analista_responsavel, _url_plano(item.plano, item=item.pk)))
        for meta in Meta.objects.filter(plano__prestacao__in=prestacoes, status_revisao=StatusRevisaoPlano.AGUARDANDO).select_related("plano__prestacao"):
            linhas.append(_linha(meta.plano.prestacao, "Preparação", "Meta", meta.descricao[:120], rotulo_revisao(meta, "meta", chaves_ratificacao(meta.plano.prestacao)), meta.plano.prestacao.analista_responsavel, _url_plano(meta.plano, secao="metas")))
    if tipo in {"", "documento"}:
        for documento in Documento.objects.ativos().filter(prestacao_contas__in=prestacoes, status_processamento="aguardando_validacao").select_related("prestacao_contas"):
            linhas.append(_linha(documento.prestacao_contas, "Documentos", "Classificação documental", documento.nome_original, "Aguardando revisão", documento.prestacao_contas.analista_responsavel, reverse("documentos:detalhe", kwargs={"pk": documento.pk})))
    return linhas


def _linha(prestacao, etapa, tipo, descricao, situacao, responsavel, url) -> dict:
    return {
        "processo": prestacao.numero_processo,
        "etapa": etapa,
        "tipo": tipo,
        "descricao": descricao,
        "situacao": situacao,
        "responsavel": responsavel.username if responsavel else "Não atribuído",
        "data": prestacao.atualizado_em,
        "url": url,
        "proxima": "Abrir o item e revisar a evidência.",
    }


def _url_plano(plano, item=None, secao="despesas") -> str:
    base = reverse("prestacoes_contas:detalhe", kwargs={"pk": plano.prestacao_id})
    consulta = f"?aba=plano&plano={plano.pk}&secao={secao}"
    if item:
        consulta += f"&item={item}"
    return base + consulta
