"""Etapas do processo. Orientam a navegação e não bloqueiam o acesso."""

from django.urls import reverse

from aplicacao.documentos.models import Documento
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, Meta


def montar_jornada(prestacao) -> list[dict]:
    documentos = Documento.objects.ativos().filter(prestacao_contas=prestacao)
    planos = prestacao.planos.all()
    itens = ItemPlanoTrabalho.objects.filter(plano__prestacao=prestacao)
    metas = Meta.objects.filter(plano__prestacao=prestacao)
    pendencias_plano = itens.filter(status_revisao=StatusRevisaoPlano.AGUARDANDO).count()
    pendencias_plano += metas.filter(status_revisao=StatusRevisaoPlano.AGUARDANDO).count()
    pendencias_plano += planos.filter(status_revisao=StatusRevisaoPlano.AGUARDANDO).count()
    responsavel = prestacao.analista_responsavel.username if prestacao.analista_responsavel_id else ""
    base = reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk})
    return [
        {
            "codigo": "preparacao",
            "titulo": "Preparação",
            "passos": [
                _passo("Identificação da parceria", f"{base}?aba=geral", prestacao.get_situacao_display(), 1, 0, responsavel, "Conferir as partes e o objeto."),
                _passo("Instrumento de parceria", reverse("instrumentos:instrumento", kwargs={"pk": prestacao.pk}), "Disponível", documentos.filter(tipo_documento="termo").count(), 0, responsavel, "Abrir o instrumento já estruturado."),
                _passo("Base Normativa aplicável", reverse("instrumentos:base_normativa", kwargs={"pk": prestacao.pk}), "Disponível", 0, 0, responsavel, "Conferir normas sem aplicá-las automaticamente."),
                _passo("Plano de Trabalho", f"{base}?aba=plano", "Extraído" if planos.exists() else "Não iniciado", itens.count(), pendencias_plano, responsavel, "Revisar metas, despesas e cronograma."),
            ],
        },
        {
            "codigo": "execucao",
            "titulo": "Execução e comprovação",
            "passos": [
                _passo("Documentos do processo", f"{base}?aba=documentos", "Em recebimento", documentos.count(), documentos.filter(status_processamento="aguardando_validacao").count(), responsavel, "Enviar ou consultar os PDFs."),
                _passo("Financeiro", f"{base}?aba=financeiro", prestacao.get_fase_display(), prestacao.despesas.count(), 0, responsavel, "Consultar despesas e movimentações já cadastradas."),
                _passo("Diligências", f"{base}?aba=geral#diligencias", "Quando necessárias", prestacao.diligencias.count(), 0, responsavel, "Abrir somente se a análise exigir."),
            ],
        },
        {
            "codigo": "analise",
            "titulo": "Análise assistida",
            "passos": [
                _passo("Verificações", f"{base}?aba=analise", "Disponível", 0, 0, responsavel, "Executar regras sem concluir a prestação."),
                _passo("Achados", f"{base}?aba=achados", "Registrados" if prestacao.achados.exists() else "Sem achados", prestacao.achados.count(), 0, responsavel, "Concordar ou discordar de cada achado."),
                _passo("Pré-análise", f"{base}?aba=pre-analise", "Separada da conclusão", prestacao.pre_analises.count(), 0, responsavel, "Ler a síntese sem tratá-la como parecer final."),
                _passo("Parecer", reverse("pareceres:parecer_final", kwargs={"prestacao_pk": prestacao.pk}), "Decisão humana", prestacao.pareceres_finais.count(), 0, responsavel, "Elaborar o parecer quando for o caso."),
            ],
        },
    ]


def _passo(titulo, url, situacao, quantidade, pendencias, responsavel, proxima) -> dict:
    return {
        "titulo": titulo,
        "url": url,
        "situacao": situacao,
        "quantidade": quantidade,
        "pendencias": pendencias,
        "responsavel": responsavel,
        "proxima": proxima,
    }
