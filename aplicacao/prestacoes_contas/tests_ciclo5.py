from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.models import Documento
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, PlanoTrabalho, PrestacaoContas
from aplicacao.prestacoes_contas.situacao_revisao import rotulo_revisao

Usuario = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"


class TesteCiclo5(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo5",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="PROC-CICLO5", criado_por=self.usuario)
        self.plano = PlanoTrabalho.objects.create(
            prestacao=self.prestacao,
            titulo="Plano sintético do ciclo",
            versao=1,
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
            cronograma=[],
            cronograma_status=StatusRevisaoPlano.AGUARDANDO,
        )
        self.elegivel = self._item(1, "Item elegível sintético", trecho="Item elegível sintético 10,00")
        self.sem_evidencia = self._item(2, "Item sem trecho", trecho="")
        self.divergente = self._item(
            3,
            "Item divergente",
            trecho="Item divergente 30,00",
            quantidade=Decimal("2.000"),
            valor_unitario=Decimal("10.00"),
            valor_previsto=Decimal("30.00"),
        )
        self.ja_decidido = self._item(4, "Item já confirmado", trecho="Item já confirmado 10,00", status=StatusRevisaoPlano.CONFIRMADO)
        self.ratificacao = self._item(5, "Item importado", trecho="Item importado 10,00")
        RegistroAuditoria.objects.create(
            evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
            descricao="Decisão importada aguardando ratificação.",
            detalhes={
                "prestacao": self.prestacao.numero_processo,
                "status_destino": StatusRevisaoPlano.AGUARDANDO,
                "pendencias": [
                    {
                        "tipo": "item",
                        "ordem": 5,
                        "pagina": 1,
                        "descricao": "Item importado",
                    }
                ],
            },
        )
        self.client.force_login(self.usuario)

    def _item(self, ordem, descricao, trecho, status=StatusRevisaoPlano.AGUARDANDO, quantidade=None, valor_unitario=None, valor_previsto=Decimal("10.00")):
        return ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            descricao=descricao,
            descricao_original=descricao,
            valor_previsto=valor_previsto,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            natureza="outro",
            ordem=ordem,
            pagina=1,
            trecho=trecho,
            status_revisao=status,
        )

    def test_cockpit_e_menu_nao_duplicam_a_jornada(self):
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertContains(resposta, "Cockpit")
        self.assertContains(resposta, "Visão 360°")
        self.assertContains(resposta, "abas-painel")
        self.assertContains(resposta, "Minha fila")
        self.assertContains(resposta, "FinOps")
        self.assertContains(resposta, "info-menu")
        self.assertContains(resposta, 'class="filtros-recolhiveis"')
        self.assertNotContains(resposta, 'filtros-recolhiveis" open')
        self.assertNotContains(resposta, 'aria-label="Abas analíticas"')

    def test_filtros_abrem_quando_ha_contexto(self):
        resposta = self.client.get(reverse("painel:inicio"), {"situacao": "em_elaboracao"})
        self.assertContains(resposta, 'class="filtros-recolhiveis" open')

    def test_jornada_abre_instrumento_normas_e_plano(self):
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "Identificação da Parceria")
        self.assertContains(resposta, reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "?aba=plano")
        self.assertContains(resposta, "FinOps")
        self.assertNotContains(resposta, "nav-pills")

    def test_integracao_nao_configurada(self):
        resposta = self.client.get(reverse("documentos:lista"))
        self.assertContains(resposta, "Não configurada")
        self.assertContains(resposta, "SIGEF")
        self.assertNotContains(resposta, "integração ativa")

    @patch("aplicacao.documentos.recebimento.processar_documento_task.delay")
    def test_upload_preserva_origem_e_usuario(self, _tarefa):
        arquivo = SimpleUploadedFile("sintetico.pdf", PDF, content_type="application/pdf")
        resposta = self.client.post(reverse("documentos:enviar", kwargs={"prestacao_pk": self.prestacao.pk}), {"arquivos": arquivo})
        self.assertEqual(resposta.status_code, 302)
        documento = Documento.objects.get(prestacao_contas=self.prestacao)
        self.assertEqual(documento.criado_por, self.usuario)
        self.assertEqual(documento.origem, "upload")
        self.assertTrue(documento.hash_sha256)

    def test_confirmacao_individual_altera_somente_o_item(self):
        self.client.post(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {"acao": "confirmar_item", "item_id": self.elegivel.pk, "retorno_secao": "despesas"},
        )
        self.elegivel.refresh_from_db()
        self.sem_evidencia.refresh_from_db()
        self.assertEqual(self.elegivel.status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertEqual(self.elegivel.revisado_por, self.usuario)
        self.assertEqual(self.sem_evidencia.status_revisao, StatusRevisaoPlano.AGUARDANDO)

    def test_lote_confirma_somente_elegiveis_selecionados(self):
        antes = self.divergente.valor_previsto
        self.client.post(
            reverse("prestacoes_contas:revisao_lote_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {
                "confirmar_lote": "1",
                "retorno_secao": "despesas",
                "item": [self.elegivel.pk, self.sem_evidencia.pk, self.divergente.pk, self.ja_decidido.pk, self.ratificacao.pk],
            },
        )
        self.elegivel.refresh_from_db()
        self.sem_evidencia.refresh_from_db()
        self.divergente.refresh_from_db()
        self.ja_decidido.refresh_from_db()
        self.ratificacao.refresh_from_db()
        self.assertEqual(self.elegivel.status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertEqual(self.sem_evidencia.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.assertEqual(self.divergente.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.assertEqual(self.divergente.valor_previsto, antes)
        self.assertEqual(self.ja_decidido.status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertIsNone(self.ja_decidido.revisado_por_id)
        self.assertEqual(self.ratificacao.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        evento = RegistroAuditoria.objects.filter(evento=RegistroAuditoria.Evento.REVISAO_HUMANA, detalhes__operacao_lote__isnull=False).latest("data_hora")
        self.assertEqual(evento.usuario, self.usuario)
        self.assertIn(self.elegivel.pk, evento.detalhes.get("confirmados", [self.elegivel.pk]))
        self.assertFalse(evento.detalhes.get("aprovacao_administrativa", True))
        self.client.post(
            reverse("prestacoes_contas:revisao_lote_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {"confirmar_lote": "1", "item": [self.elegivel.pk]},
        )
        self.assertEqual(RegistroAuditoria.objects.filter(detalhes__acao="confirmar_itens_elegiveis", detalhes__item=self.elegivel.pk).count(), 1)

    def test_rejeicao_individual_preserva_o_valor(self):
        self.client.post(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk}),
            {"acao": "rejeitar_item", "item_id": self.sem_evidencia.pk, "justificativa": "Não corresponde ao plano.", "retorno_secao": "despesas"},
        )
        self.sem_evidencia.refresh_from_db()
        self.elegivel.refresh_from_db()
        self.assertEqual(self.sem_evidencia.status_revisao, StatusRevisaoPlano.REJEITADO)
        self.assertEqual(self.sem_evidencia.valor_previsto, Decimal("10.00"))
        self.assertEqual(self.elegivel.status_revisao, StatusRevisaoPlano.AGUARDANDO)

    def test_rotulo_nao_grava_estado(self):
        self.assertEqual(rotulo_revisao(self.ratificacao, "item", {( "item", 5, 1, "Item importado")}), "Pendente de ratificação de decisão importada")
        self.ratificacao.refresh_from_db()
        self.assertEqual(self.ratificacao.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        resposta = self.client.get(reverse("painel:pendencias"))
        self.assertContains(resposta, "Pendente de ratificação de decisão importada")
        self.assertContains(resposta, "Informação ausente")
        self.assertContains(resposta, "Divergente ou não conclusivo")
