from django.test import Client, TestCase
from django.urls import reverse

from aplicacao.achados.models import Achado
from aplicacao.diligencias.escolhas import MotivoDiligencia, SituacaoDiligencia
from aplicacao.diligencias.models import HistoricoDiligencia
from aplicacao.diligencias.servico import abrir_diligencia
from aplicacao.painel.consultas.escopo import filtros_com_escopo
from aplicacao.painel.consultas.filtros import FiltrosPainel
from aplicacao.painel.consultas.recortes import prestacoes
from aplicacao.painel.consultas.visao import montar_visao, opcoes_de_filtro
from aplicacao.pareceres.models import HistoricoParecerFinal
from aplicacao.pareceres.parecer_final import (
    finalizar_parecer,
    obter_ou_criar_parecer,
    registrar_sugestao_ia,
    salvar_texto_analista,
)
from aplicacao.prestacoes_contas.atribuicao import atribuir_analista
from aplicacao.prestacoes_contas.models import HistoricoAtribuicaoPrestacao, PrestacaoContas
from aplicacao.usuarios.acesso import (
    pode_atuar_na_prestacao,
    pode_distribuir_processos,
    pode_gerenciar_usuarios,
    pode_ver_prestacao,
    possui_visao_transversal,
    prestacoes_visiveis,
)
from aplicacao.usuarios.models import Usuario


def _usuario(username, perfil):
    return Usuario.objects.create_user(
        username=username,
        password="Isolada-apenas-no-teste",
        perfil=perfil,
        is_staff=perfil == Usuario.Perfil.ADMINISTRADOR,
        is_superuser=perfil == Usuario.Perfil.ADMINISTRADOR,
    )


class TestePerfisResponsabilidade(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = _usuario("adm-matriz", Usuario.Perfil.ADMINISTRADOR)
        cls.auditor = _usuario("aud-matriz", Usuario.Perfil.AUDITOR)
        cls.analista_a = _usuario("ana-a-matriz", Usuario.Perfil.ANALISTA)
        cls.analista_b = _usuario("ana-b-matriz", Usuario.Perfil.ANALISTA)
        cls.consulta = _usuario("consulta-matriz", Usuario.Perfil.CONSULTA)
        cls.proc_a = PrestacaoContas.objects.create(
            numero_processo="PROC-ANA-A",
            analista_responsavel=cls.analista_a,
            criado_por=cls.admin,
        )
        cls.proc_b = PrestacaoContas.objects.create(
            numero_processo="PROC-ANA-B",
            analista_responsavel=cls.analista_b,
            criado_por=cls.admin,
        )
        Achado.objects.create(
            prestacao_contas=cls.proc_a,
            codigo="ACH-A-1",
            titulo="Achado do processo A",
            descricao_factual="somente A",
            chave_consolidacao="chave-a-1",
        )
        Achado.objects.create(
            prestacao_contas=cls.proc_b,
            codigo="ACH-B-1",
            titulo="Achado do processo B",
            descricao_factual="somente B",
            chave_consolidacao="chave-b-1",
        )

    def _cliente(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def test_helpers_matriz(self):
        self.assertTrue(pode_gerenciar_usuarios(self.admin))
        self.assertFalse(pode_gerenciar_usuarios(self.auditor))
        self.assertFalse(pode_gerenciar_usuarios(self.analista_a))
        self.assertTrue(pode_distribuir_processos(self.admin))
        self.assertTrue(pode_distribuir_processos(self.auditor))
        self.assertFalse(pode_distribuir_processos(self.analista_a))
        self.assertTrue(pode_ver_prestacao(self.admin, self.proc_b))
        self.assertTrue(pode_ver_prestacao(self.auditor, self.proc_b))
        self.assertTrue(pode_ver_prestacao(self.analista_a, self.proc_a))
        self.assertFalse(pode_ver_prestacao(self.analista_a, self.proc_b))
        self.assertTrue(pode_atuar_na_prestacao(self.analista_a, self.proc_a))
        self.assertFalse(pode_atuar_na_prestacao(self.analista_a, self.proc_b))
        self.assertTrue(pode_atuar_na_prestacao(self.auditor, self.proc_b))
        self.assertFalse(pode_gerenciar_usuarios(self.consulta))
        self.assertFalse(pode_distribuir_processos(self.consulta))
        self.assertFalse(pode_atuar_na_prestacao(self.consulta, self.proc_a))
        # Legado: ainda lê transversalmente; remoção completa da visão aguarda decisão.
        self.assertTrue(possui_visao_transversal(self.consulta))
        self.assertTrue(pode_ver_prestacao(self.consulta, self.proc_a))

    def test_analista_nao_abre_processo_de_outro(self):
        cliente = self._cliente(self.analista_a)
        resposta = cliente.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.proc_b.pk}))
        self.assertEqual(resposta.status_code, 403)

    def test_analista_abre_processo_proprio(self):
        cliente = self._cliente(self.analista_a)
        resposta = cliente.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.proc_a.pk}))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "PROC-ANA-A")

    def test_analista_nao_altera_processo_de_outro(self):
        cliente = self._cliente(self.analista_a)
        resposta = cliente.post(
            reverse("prestacoes_contas:incluir_despesa", kwargs={"pk": self.proc_b.pk}),
            data={},
        )
        self.assertEqual(resposta.status_code, 403)

    def test_analista_nao_acessa_admin_nem_saude_nem_redistribui(self):
        cliente = self._cliente(self.analista_a)
        self.assertEqual(cliente.get(reverse("painel:administracao")).status_code, 403)
        self.assertEqual(cliente.get(reverse("painel:saude")).status_code, 403)
        self.assertEqual(cliente.get(reverse("usuarios:lista")).status_code, 403)
        self.assertEqual(
            cliente.post(
                reverse("prestacoes_contas:atribuir", kwargs={"pk": self.proc_a.pk}),
                data={"analista": self.analista_b.pk, "justificativa": "tentativa"},
            ).status_code,
            403,
        )

    def test_auditor_ve_processos_de_analistas_diferentes_e_redistribui(self):
        cliente = self._cliente(self.auditor)
        self.assertEqual(cliente.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.proc_a.pk})).status_code, 200)
        self.assertEqual(cliente.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.proc_b.pk})).status_code, 200)
        resposta = cliente.post(
            reverse("prestacoes_contas:atribuir", kwargs={"pk": self.proc_b.pk}),
            data={"analista": self.analista_a.pk, "justificativa": "Redistribuição de teste"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.proc_b.refresh_from_db()
        self.assertEqual(self.proc_b.analista_responsavel_id, self.analista_a.pk)
        self.assertTrue(
            HistoricoAtribuicaoPrestacao.objects.filter(
                prestacao=self.proc_b,
                analista_anterior=self.analista_b,
                analista_novo=self.analista_a,
                alterado_por=self.auditor,
            ).exists()
        )

    def test_auditor_nao_administra_usuarios(self):
        cliente = self._cliente(self.auditor)
        self.assertEqual(cliente.get(reverse("usuarios:lista")).status_code, 403)
        self.assertEqual(cliente.get(reverse("painel:administracao")).status_code, 403)

    def test_admin_acessa_usuarios_e_lista_completa(self):
        cliente = self._cliente(self.admin)
        self.assertEqual(cliente.get(reverse("usuarios:lista")).status_code, 200)
        lista = cliente.get(reverse("prestacoes_contas:lista"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "PROC-ANA-A")
        self.assertContains(lista, "PROC-ANA-B")

    def test_lista_analista_so_mostra_atribuidos(self):
        cliente = self._cliente(self.analista_a)
        lista = cliente.get(reverse("prestacoes_contas:lista"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "PROC-ANA-A")
        self.assertNotContains(lista, "PROC-ANA-B")
        ids = set(prestacoes_visiveis(self.analista_a).values_list("id", flat=True))
        self.assertEqual(ids, {self.proc_a.pk})

    def test_api_respeita_escopo_do_analista(self):
        cliente = self._cliente(self.analista_a)
        lista = cliente.get("/api/prestacoes/")
        self.assertEqual(lista.status_code, 200)
        numeros = {item["numero_processo"] for item in lista.json()}
        self.assertEqual(numeros, {"PROC-ANA-A"})
        detalhe = cliente.get(f"/api/prestacoes/{self.proc_b.pk}/")
        self.assertEqual(detalhe.status_code, 404)

    def test_atribuicao_preserva_historico_anterior(self):
        atribuir_analista(
            prestacao=self.proc_a,
            analista_novo=self.analista_b,
            alterado_por=self.admin,
            justificativa="Primeira redistribuição",
        )
        atribuir_analista(
            prestacao=self.proc_a,
            analista_novo=self.analista_a,
            alterado_por=self.auditor,
            justificativa="Retorno",
        )
        historico = list(
            HistoricoAtribuicaoPrestacao.objects.filter(prestacao=self.proc_a).order_by("criado_em", "id")
        )
        self.assertGreaterEqual(len(historico), 2)
        self.assertEqual(historico[-2].analista_novo_id, self.analista_b.pk)
        self.assertEqual(historico[-1].analista_anterior_id, self.analista_b.pk)
        self.assertEqual(historico[-1].analista_novo_id, self.analista_a.pk)

    def test_painel_360_analista_nao_ve_agregacao_alheia(self):
        filtros_a = filtros_com_escopo(self.analista_a, FiltrosPainel())
        painel_a = montar_visao(filtros_a)
        self.assertEqual(prestacoes(filtros_a).count(), 1)
        self.assertEqual({p.numero_processo for p in prestacoes(filtros_a)}, {"PROC-ANA-A"})
        self.assertTrue(painel_a.kpis)
        opcoes = opcoes_de_filtro("visao", usuario=self.analista_a, filtros=filtros_a)
        numeros = {numero for _, numero in opcoes["prestacoes"]}
        self.assertEqual(numeros, {"PROC-ANA-A"})
        self.assertNotIn("PROC-ANA-B", numeros)

        cliente = self._cliente(self.analista_a)
        pagina = cliente.get(reverse("painel:inicio"))
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, "PROC-ANA-B")
        self.assertNotContains(pagina, "Achado do processo B")

        filtros_aud = filtros_com_escopo(self.auditor, FiltrosPainel())
        self.assertEqual(prestacoes(filtros_aud).count(), 2)
        pagina_aud = self._cliente(self.auditor).get(reverse("painel:inicio"))
        self.assertEqual(pagina_aud.status_code, 200)

    def test_diligencia_fluxo_e_isolamento(self):
        dil = abrir_diligencia(
            prestacao=self.proc_a,
            usuario=self.analista_a,
            motivo=MotivoDiligencia.AUSENCIA_DOCUMENTO,
            descricao="Falta extrato",
        )
        self.assertEqual(dil.situacao, SituacaoDiligencia.ABERTA)
        self.assertTrue(HistoricoDiligencia.objects.filter(diligencia=dil).exists())

        cliente_a = self._cliente(self.analista_a)
        self.assertEqual(cliente_a.get(reverse("diligencias:detalhe", kwargs={"pk": dil.pk})).status_code, 200)
        nova = cliente_a.post(
            reverse("diligencias:nova", kwargs={"prestacao_pk": self.proc_a.pk}),
            data={
                "motivo": MotivoDiligencia.INFORMACAO_INCOMPLETA,
                "descricao": "Complementar dados",
            },
        )
        self.assertEqual(nova.status_code, 302)

        cliente_b = self._cliente(self.analista_b)
        self.assertEqual(cliente_b.get(reverse("diligencias:detalhe", kwargs={"pk": dil.pk})).status_code, 403)
        self.assertEqual(
            cliente_b.get(reverse("diligencias:nova", kwargs={"prestacao_pk": self.proc_a.pk})).status_code,
            403,
        )
        self.assertEqual(self._cliente(self.auditor).get(reverse("diligencias:detalhe", kwargs={"pk": dil.pk})).status_code, 200)

    def test_parecer_final_tres_areas_e_isolamento(self):
        parecer = obter_ou_criar_parecer(prestacao=self.proc_a, usuario=self.analista_a)
        registrar_sugestao_ia(parecer=parecer, usuario=self.analista_a, texto="Sugestão de apoio do sistema")
        salvar_texto_analista(parecer=parecer, usuario=self.analista_a, texto="Texto elaborado pelo analista")
        finalizar_parecer(parecer=parecer, usuario=self.analista_a, texto_final="Versão final humana")
        parecer.refresh_from_db()
        self.assertEqual(parecer.sugestao_ia, "Sugestão de apoio do sistema")
        self.assertEqual(parecer.texto_analista, "Texto elaborado pelo analista")
        self.assertEqual(parecer.texto_final, "Versão final humana")
        self.assertTrue(HistoricoParecerFinal.objects.filter(parecer=parecer).exists())

        cliente_a = self._cliente(self.analista_a)
        pagina = cliente_a.get(reverse("pareceres:parecer_final", kwargs={"prestacao_pk": self.proc_a.pk}))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Sugestão da IA")
        self.assertContains(pagina, "Texto do analista")
        self.assertContains(pagina, "Versão final")
        self.assertContains(pagina, "responsabilidade humana")

        cliente_b = self._cliente(self.analista_b)
        self.assertEqual(
            cliente_b.get(reverse("pareceres:parecer_final", kwargs={"prestacao_pk": self.proc_a.pk})).status_code,
            403,
        )

    def test_formulario_usuario_nao_oferece_consulta(self):
        cliente = self._cliente(self.admin)
        pagina = cliente.get(reverse("usuarios:novo"))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Administrador")
        self.assertContains(pagina, "Auditor")
        self.assertContains(pagina, "Analista")
        self.assertNotContains(pagina, 'value="CONSULTA"')
        # Em criação não deve haver opção de atribuir Consulta.
        self.assertNotContains(pagina, "Consulta (legado")
