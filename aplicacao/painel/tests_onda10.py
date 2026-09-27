import os
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase

RAIZ = Path(__file__).resolve().parents[2]


class TesteReleaseOnda10(SimpleTestCase):
    def test_versao_da_release(self):
        from aplicacao.configuracao.versao import ONDA_ATUAL, VERSAO_APLICACAO

        self.assertEqual(VERSAO_APLICACAO, "1.0.0-rc1")
        self.assertEqual(ONDA_ATUAL, 10)

    def test_cookie_seguro_exige_variavel(self):
        from aplicacao.configuracao.settings import cookies_seguros_habilitados, proxy_reverso_habilitado

        with mock.patch.dict(os.environ, {"COOKIES_SEGUROS": "false", "BEHIND_PROXY": "false"}):
            self.assertFalse(cookies_seguros_habilitados())
            self.assertFalse(proxy_reverso_habilitado())
        with mock.patch.dict(os.environ, {"COOKIES_SEGUROS": "true", "BEHIND_PROXY": "true"}):
            self.assertTrue(cookies_seguros_habilitados())
            self.assertTrue(proxy_reverso_habilitado())

    def test_compose_nao_publica_banco_nem_redis(self):
        texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertEqual(texto.count("cge_aplicacao:onda10-rc1"), 3)
        self.assertNotIn("5432:", texto)
        self.assertNotIn("6379:", texto)
        self.assertNotIn(":latest", texto)

    def test_exemplo_de_ambiente_sem_segredo(self):
        texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
        self.assertIn("COOKIES_SEGUROS=false", texto)
        self.assertIn("BEHIND_PROXY=false", texto)
        self.assertIn("altere_esta_senha", texto)
        self.assertNotIn("sk-", texto)
        self.assertNotIn("Bearer ", texto)

    def test_entrada_usa_a_onda_corrente(self):
        resposta = self.client.get("/entrar/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Versão 1.0.0-rc1")
        self.assertContains(resposta, "Onda 10")
        self.assertNotContains(resposta, "Onda 9")
        for relativo in (
            "aplicacao/templates/painel/entrar.html",
            "aplicacao/templates/painel/administracao.html",
            "aplicacao/templates/inteligencia_artificial/consumo.html",
        ):
            self.assertNotIn("Onda 9", (RAIZ / relativo).read_text(encoding="utf-8"))

    def test_periodo_permanece_empilhado(self):
        html = (RAIZ / "aplicacao/templates/painel/_filtros.html").read_text(encoding="utf-8")
        css = (RAIZ / "aplicacao/static/css/cge.css").read_text(encoding="utf-8")
        self.assertLess(html.index('for="id-inicio"'), html.index('for="id-fim"'))
        self.assertIn("flex-direction: column", css)


class TesteSaudeDaRelease(TestCase):
    def test_migrations_aplicadas_nao_fingem_pendencia(self):
        from aplicacao.painel.saude import coletar_saude

        nomes = {item.nome: item for item in coletar_saude()}
        self.assertEqual(nomes["Migrations"].estado, "Operacional")
        self.assertIn("1.0.0-rc1", nomes["Aplicação Django"].detalhe)
        self.assertEqual(nomes["Celery Beat"].estado, "Não verificado")
