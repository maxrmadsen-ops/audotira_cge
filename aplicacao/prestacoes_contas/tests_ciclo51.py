from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, PlanoTrabalho, PrestacaoContas

Usuario = get_user_model()


class TesteCiclo51(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo51",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.alheio = Usuario.objects.create_user(
            username="analista-alheio-51",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="PROC-CICLO51", criado_por=self.usuario)
        self.plano = PlanoTrabalho.objects.create(
            prestacao=self.prestacao,
            titulo="Plano sintético da conferência",
            versao=1,
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
            cronograma=[],
            cronograma_status=StatusRevisaoPlano.AGUARDANDO,
        )
        self.primeiro = self._item(1, "Primeira despesa sintética")
        self.segundo = self._item(2, "Segunda despesa sintética")
        self.client.force_login(self.usuario)

    def _item(self, ordem, descricao):
        return ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            descricao=descricao,
            descricao_original=descricao,
            valor_previsto=Decimal("10.00"),
            natureza="outro",
            ordem=ordem,
            pagina=1,
            trecho=f"{descricao} 10,00",
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
        )

    def test_menu_sem_processo_nao_mostra_atalhos_contextuais(self):
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertContains(resposta, "Painel Geral")
        self.assertContains(resposta, "Minha fila")
        self.assertContains(resposta, "Base Normativa Institucional")
        self.assertContains(resposta, "Governança e configurações")
        self.assertContains(resposta, "FinOps")
        self.assertNotContains(resposta, "Etapa de Preparação")

    def test_menu_do_processo_destaca_a_etapa_atual(self):
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "Etapa de Preparação")
        self.assertContains(resposta, "Etapa de Execução")
        self.assertContains(resposta, "Análise Assistida")
        self.assertContains(resposta, "Trocar processo")
        self.assertContains(resposta, 'aria-current="page"')
        self.assertContains(resposta, "Identificação dos Envolvidos")
        self.assertContains(resposta, "Documentos do Processo")
        self.assertContains(resposta, "Classificação e Extração")
        self.assertNotContains(resposta, "nav-pills")
        self.client.force_login(self.alheio)
        self.assertEqual(self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk})).status_code, 403)

    def test_rotas_antigas_chegam_aos_paineis(self):
        self.assertRedirects(
            self.client.get(reverse("instrumentos:preparacao", kwargs={"pk": self.prestacao.pk})),
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
        )
        plano = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}), {"aba": "plano"})
        self.assertContains(plano, "Resumo")
        self.assertContains(plano, "Metas e etapas")
        self.assertContains(plano, "Despesas previstas")
        self.assertContains(plano, "Cronograma")
        self.assertContains(plano, "Documento original")
        antigo = self.client.get(
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
            {"aba": "plano", "secao": "despesas", "item": self.primeiro.pk},
        )
        self.assertRedirects(
            antigo,
            reverse("prestacoes_contas:conferencia_despesas", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk})
            + f"?item={self.primeiro.pk}",
        )

    def test_conferencia_navega_sem_gravar_e_reusa_a_revisao(self):
        url = reverse("prestacoes_contas:conferencia_despesas", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk})
        antes = RegistroAuditoria.objects.count()
        resposta = self.client.get(url)
        self.assertContains(resposta, "Item 1 de 2")
        self.assertContains(resposta, "Primeira despesa sintética")
        self.assertContains(resposta, "Confirmar")
        self.assertContains(resposta, "Manter pendente")
        self.primeiro.refresh_from_db()
        self.assertEqual(self.primeiro.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.assertEqual(RegistroAuditoria.objects.count(), antes)
        seguinte = self.client.get(url, {"item": self.segundo.pk})
        self.assertContains(seguinte, "Item 2 de 2")
        self.segundo.refresh_from_db()
        self.assertEqual(self.segundo.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.client.post(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {"acao": "confirmar_item", "item_id": self.primeiro.pk, "retorno": "conferencia"},
        )
        self.primeiro.refresh_from_db()
        self.segundo.refresh_from_db()
        self.assertEqual(self.primeiro.status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertEqual(self.primeiro.revisado_por, self.usuario)
        self.assertEqual(self.segundo.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.client.post(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {"acao": "corrigir_item", "item_id": self.segundo.pk, "descricao": "Segunda despesa sintética", "valor_previsto": "10.00", "retorno": "conferencia"},
        )
        self.segundo.refresh_from_db()
        self.assertEqual(self.segundo.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.client.post(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {
                "acao": "rejeitar_item",
                "item_id": self.segundo.pk,
                "justificativa": "Não corresponde ao documento.",
                "retorno": "conferencia",
            },
        )
        self.segundo.refresh_from_db()
        self.assertEqual(self.segundo.status_revisao, StatusRevisaoPlano.REJEITADO)
        self.assertEqual(self.segundo.valor_previsto, Decimal("10.00"))
        evento = RegistroAuditoria.objects.filter(detalhes__acao="rejeitar_item", detalhes__item=self.segundo.pk).latest("data_hora")
        self.assertEqual(evento.usuario, self.usuario)
        self.assertEqual(evento.detalhes.get("justificativa"), "Não corresponde ao documento.")

    def test_etapa_futura_nao_simula_o_fluxo(self):
        resposta = self.client.get(
            reverse("prestacoes_contas:etapa_futura", kwargs={"pk": self.prestacao.pk, "slug": "prestacoes-parciais"})
        )
        self.assertContains(resposta, "Etapa futura")
        self.assertContains(resposta, "Documentos")
        self.assertNotContains(resposta, "Concluir prestação")
        self.client.force_login(self.alheio)
        self.assertEqual(
            self.client.get(reverse("prestacoes_contas:conferencia_despesas", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk})).status_code,
            403,
        )

    def test_conferencia_empilha_em_tela_estreita(self):
        from pathlib import Path

        css = Path("aplicacao/static/css/cge.css").read_text(encoding="utf-8")
        self.assertIn(".conferencia { grid-template-columns: 1fr; }", css)
        self.assertLess(css.find("@media (max-width: 991px)"), css.rfind(".conferencia { grid-template-columns: 1fr; }"))
