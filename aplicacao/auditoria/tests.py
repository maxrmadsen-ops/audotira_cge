from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria

Usuario = get_user_model()


class TesteAuditoria(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ADMINISTRADOR,
            is_staff=True,
            is_superuser=True,
        )
        self.consulta = Usuario.objects.create_user(
            username="consulta",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.CONSULTA,
        )

    def test_login_gera_registro(self):
        self.client.login(username="admin", password="Isolada-apenas-no-teste")
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                evento=RegistroAuditoria.Evento.LOGIN,
                usuario=self.administrador,
            ).exists()
        )

    def test_falha_de_login_nao_grava_senha(self):
        self.client.login(username="admin", password="senha-incorreta")
        registro = RegistroAuditoria.objects.get(evento=RegistroAuditoria.Evento.FALHA_LOGIN)
        texto = str(registro.detalhes)
        self.assertNotIn("senha-incorreta", texto)
        self.assertNotIn("password", registro.detalhes)
        self.assertEqual(registro.detalhes["usuario_informado"], "admin")

    def test_consulta_nao_lista_registros(self):
        self.client.force_login(self.consulta)
        resposta = self.client.get(reverse("auditoria:registros"))
        self.assertEqual(resposta.status_code, 403)

    def test_administrador_lista_registros(self):
        self.client.force_login(self.administrador)
        resposta = self.client.get(reverse("auditoria:registros"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Registros de auditoria")
