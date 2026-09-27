from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from aplicacao.painel.saude import coletar_saude

Usuario = get_user_model()


class TesteFundacao(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ADMINISTRADOR,
            is_staff=True,
        )
        self.consulta = Usuario.objects.create_user(
            username="consulta",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.CONSULTA,
        )

    def test_extensao_pgvector_habilitada(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = %s", ["vector"])
            self.assertIsNotNone(cursor.fetchone())

    def test_sonda_viva_sem_autenticacao(self):
        resposta = self.client.get(reverse("painel:viva"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["aplicacao"], "operacional")

    def test_painel_exige_login(self):
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/entrar/", resposta["Location"])

    def test_login_e_painel_sem_dados_ficticios(self):
        self.client.force_login(self.administrador)
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Aguardando próximas ondas")
        self.assertNotContains(resposta, "2022TR000929")

    def test_consulta_nao_abre_administracao_nem_saude(self):
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse("painel:administracao")).status_code, 403)
        self.assertEqual(self.client.get(reverse("painel:saude")).status_code, 403)

    def test_administrador_abre_saude(self):
        self.client.force_login(self.administrador)
        with patch("aplicacao.painel.views.coletar_saude", return_value=[]):
            resposta = self.client.get(reverse("painel:saude"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Saúde do Sistema")

    def test_modulo_futuro_nao_finge_funcionalidade(self):
        self.client.force_login(self.consulta)
        resposta = self.client.get(reverse("painel:modulo", kwargs={"slug": "pre-analises"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "ainda não está disponível")
        self.assertEqual(self.client.get(reverse("painel:modulo", kwargs={"slug": "inexistente"})).status_code, 404)

    def test_coleta_de_saude_nao_simula_provedores(self):
        nomes = {item.nome: item.estado for item in coletar_saude()}
        self.assertEqual(nomes["PostgreSQL"], "Operacional")
        self.assertEqual(nomes["OpenAI"], "Não configurado")
        self.assertEqual(nomes["Anthropic"], "Não configurado")
        self.assertIn(nomes["Redis"], {"Operacional", "Indisponível"})
        self.assertIn(nomes["Celery Worker"], {"Operacional", "Indisponível"})
