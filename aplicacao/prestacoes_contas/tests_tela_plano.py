from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.prestacoes_contas.apresentacao_plano import etapas_legiveis, parametros_legiveis, rotulo_milhar
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, Meta, PlanoTrabalho, PrestacaoContas

Usuario = get_user_model()

ETAPAS_BRUTAS = (
    "Detalhe Relatorio Ano Base Listar Plano Trabalho Metas Descrição Atendimento sintetico "
    "Data Início 01/01/2024 Forma de Execução pagamento mensal "
    "Parametros de Aferição Relatórios internos Adesão, execução e encerramento"
)


class TesteTelaPlano(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-tela-plano",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="PROC-TELA-PLANO", criado_por=self.usuario)
        self.plano = PlanoTrabalho.objects.create(
            prestacao=self.prestacao,
            titulo="Plano sintético de atendimento",
            versao=1,
            objeto="Objeto sintético",
            valor_global=Decimal("350.00"),
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
            cronograma=[
                {"ano": 2024, "mes": "Junho", "repasse": "200.00", "contrapartida": "0.00", "pagina": 2, "trecho": "Junho 200,00 0,00"},
                {"ano": 2024, "mes": "Julho", "repasse": "0.00", "contrapartida": "0.00", "pagina": 2, "trecho": "Julho 0,00 0,00"},
            ],
            cronograma_status=StatusRevisaoPlano.AGUARDANDO,
        )
        self.apoio = ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            descricao="Apoio pedagógico sintético",
            descricao_original="Apoio pedagógico sintético",
            valor_previsto=Decimal("300.00"),
            natureza="pessoal",
            ordem=1,
            pagina=3,
            trecho="Apoio pedagógico sintético 300,00",
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
        )
        self.encargo = ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            descricao="Recolhimento sintético",
            descricao_original="Recolhimento sintético",
            valor_previsto=Decimal("50.00"),
            natureza="encargo",
            ordem=2,
            pagina=4,
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
        )
        Meta.objects.create(
            plano=self.plano,
            descricao="Meta sintética de atendimento",
            forma_execucao="pagamento mensal",
            parametros_afericao="Relatórios internos",
            etapas=ETAPAS_BRUTAS,
            status_revisao=StatusRevisaoPlano.CONFIRMADO,
            pagina=2,
        )
        self.client.force_login(self.usuario)

    def test_etapas_legiveis_separam_o_cabecalho(self):
        self.assertEqual(etapas_legiveis(ETAPAS_BRUTAS, "Relatórios internos"), "Adesão, execução e encerramento")
        grudado = "Relatórios internos.Adesão, execução e encerramento"
        bruto = "Detalhe Relatorio Parametros de Aferição " + grudado
        self.assertEqual(etapas_legiveis(bruto, grudado), "Adesão, execução e encerramento")
        self.assertEqual(parametros_legiveis(grudado), "Relatórios internos.")

    def test_rotulo_de_milhar_resume_sem_apagar_centavos(self):
        self.assertEqual(rotulo_milhar(Decimal("172600")), ("173", "mil"))
        self.assertEqual(rotulo_milhar(Decimal("200")), ("200,00", ""))
        self.assertEqual(rotulo_milhar(Decimal("0")), ("", ""))

    def test_aba_mostra_conciliacao_e_preserva_a_revisao(self):
        antes = RegistroAuditoria.objects.count()
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}), {"aba": "plano"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Conciliação matemática")
        self.assertContains(resposta, "R$ 350,00")
        self.assertContains(resposta, "Adicionar manualmente")
        self.assertContains(resposta, '<details class="cartao plano-manual mt-3">')
        self.assertNotContains(resposta, '<details class="cartao plano-manual mt-3" open')
        self.assertContains(resposta, "Uma soma correta não valida o plano.")
        metas = self.client.get(
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
            {"aba": "plano", "secao": "metas"},
        )
        texto = metas.content.decode()
        self.assertIn("Adesão, execução e encerramento", texto.split("Texto original da extração")[0])
        self.assertNotIn("Listar Plano Trabalho", texto.split("Texto original da extração")[0])
        self.assertIn("Listar Plano Trabalho", texto)
        despesas = self.client.get(
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
            {"aba": "plano", "secao": "despesas", "q": "Recolhimento"},
        )
        self.assertContains(despesas, "Recolhimento sintético")
        self.assertNotContains(despesas, "Apoio pedagógico sintético")
        cronograma = self.client.get(
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
            {"aba": "plano", "secao": "cronograma"},
        )
        self.assertContains(cronograma, "plano-linha-tempo")
        self.assertContains(cronograma, "com-valor", count=1)
        self.assertContains(cronograma, "200,00")
        self.assertContains(cronograma, "Jul")
        self.assertContains(cronograma, "Tabela completa, com os meses de valor zero")
        self.apoio.refresh_from_db()
        self.assertEqual(self.apoio.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.assertEqual(Meta.objects.get(plano=self.plano).status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertEqual(RegistroAuditoria.objects.count(), antes)
        self.assertEqual(resposta.headers.get("X-Frame-Options"), "DENY")

    def test_rota_antiga_abre_a_mesma_central(self):
        resposta = self.client.get(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": self.prestacao.pk, "plano_pk": self.plano.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("aba=plano", resposta.url)
        self.assertEqual(ItemPlanoTrabalho.objects.filter(status_revisao=StatusRevisaoPlano.AGUARDANDO).count(), 2)
