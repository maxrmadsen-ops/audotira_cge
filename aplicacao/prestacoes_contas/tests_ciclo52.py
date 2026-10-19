from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import Despesa, ItemPlanoTrabalho, PlanoTrabalho, PrestacaoContas

Usuario = get_user_model()


class TesteCiclo52(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo52",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="PROC-CICLO52", criado_por=self.usuario)
        self.plano = PlanoTrabalho.objects.create(
            prestacao=self.prestacao,
            titulo="Plano sintético dos indicadores",
            versao=1,
            valor_global=Decimal("100.00"),
        )
        self.confirmado = ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            descricao="Item com extração confirmada",
            valor_previsto=Decimal("30.00"),
            natureza="outro",
            ordem=1,
            status_revisao=StatusRevisaoPlano.CONFIRMADO,
        )
        self.pendente = ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            descricao="Item ainda pendente",
            valor_previsto=Decimal("70.00"),
            natureza="outro",
            ordem=2,
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
        )
        Despesa.objects.create(prestacao=self.prestacao, item_plano=self.confirmado, valor=Decimal("5.00"), descricao="Lançamento sintético")
        self.client.force_login(self.usuario)

    def test_extracao_validada_nao_e_execucao(self):
        self.assertEqual(self.prestacao.valor_planejado, Decimal("100.00"))
        self.assertEqual(self.prestacao.valor_extracao_validada, Decimal("30.00"))
        self.assertEqual(self.prestacao.valor_previsto, Decimal("30.00"))
        self.assertEqual(self.prestacao.valor_executado, Decimal("5.00"))
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "Total previsto no Plano de Trabalho")
        self.assertContains(resposta, "R$ 100,00")
        self.assertContains(resposta, "Valor previsto com extração validada")
        self.assertContains(resposta, "R$ 30,00")
        self.assertContains(resposta, "Não representa execução ou comprovação financeira.")
        self.assertContains(resposta, "Execução financeira: Ainda não apurada")
        self.assertContains(resposta, "Despesas comprovadas: Ainda não apuradas")
        self.assertNotContains(resposta, "Previsto × executado")
        self.assertNotContains(resposta, "Executado")
        self.assertNotContains(resposta, "R$ 5,00")
        self.assertNotContains(resposta, "R$ 0,00")
        self.confirmado.refresh_from_db()
        self.pendente.refresh_from_db()
        self.assertEqual(self.confirmado.status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertEqual(self.confirmado.valor_previsto, Decimal("30.00"))
        self.assertEqual(self.pendente.status_revisao, StatusRevisaoPlano.AGUARDANDO)

    def test_financeiro_nao_trata_ausencia_como_zero(self):
        vazia = PrestacaoContas.objects.create(numero_processo="PROC-CICLO52-VAZIA", criado_por=self.usuario)
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": vazia.pk}), {"aba": "financeiro"})
        self.assertContains(resposta, "ainda não foram apuradas")
        self.assertContains(resposta, "Ainda não apuradas.")
        self.assertNotContains(resposta, "Nenhuma despesa")
        self.assertNotContains(resposta, "R$ 0,00")

    def test_menu_separa_futuro_parcial_e_operacional(self):
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "item-futuro")
        self.assertContains(resposta, "Etapa futura")
        self.assertContains(resposta, "item-parcial")
        self.assertContains(resposta, "Disponível parcialmente")
        self.assertContains(resposta, "Prestações de Contas Parciais")
        self.assertContains(resposta, 'aria-current="page"')
        css = Path("aplicacao/static/css/cge.css").read_text(encoding="utf-8")
        self.assertIn("--sidebar: 19rem", css)
        self.assertIn(".item-menu.item-futuro > a", css)
        self.assertIn(".menu-lateral.recolhido { width: 4.25rem; }", css)
        self.assertIn("min(18rem, 88vw)", css)
