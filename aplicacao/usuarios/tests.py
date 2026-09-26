from django.test import TestCase

from aplicacao.usuarios.acesso import (
    pode_administrar,
    pode_consultar,
    pode_executar_analise,
    pode_validar_analise,
)
from aplicacao.usuarios.models import Usuario


class TestePerfis(TestCase):
    def criar(self, username: str, perfil: str) -> Usuario:
        return Usuario.objects.create_user(
            username=username,
            password="Isolada-apenas-no-teste",
            perfil=perfil,
        )

    def test_perfil_padrao_e_consulta(self):
        usuario = Usuario.objects.create_user(username="novo", password="Isolada-apenas-no-teste")
        self.assertEqual(usuario.perfil, Usuario.Perfil.CONSULTA)

    def test_quatro_perfis_existem(self):
        self.assertEqual(
            set(Usuario.Perfil.values),
            {"ADMINISTRADOR", "AUDITOR", "ANALISTA", "CONSULTA"},
        )

    def test_consulta_somente_leitura(self):
        usuario = self.criar("consulta", Usuario.Perfil.CONSULTA)
        self.assertTrue(pode_consultar(usuario))
        self.assertFalse(pode_executar_analise(usuario))
        self.assertFalse(pode_validar_analise(usuario))
        self.assertFalse(pode_administrar(usuario))

    def test_analista_executa_sem_validar(self):
        usuario = self.criar("analista", Usuario.Perfil.ANALISTA)
        self.assertTrue(pode_executar_analise(usuario))
        self.assertFalse(pode_validar_analise(usuario))
        self.assertFalse(pode_administrar(usuario))

    def test_auditor_valida_sem_administrar(self):
        usuario = self.criar("auditor", Usuario.Perfil.AUDITOR)
        self.assertTrue(pode_executar_analise(usuario))
        self.assertTrue(pode_validar_analise(usuario))
        self.assertFalse(pode_administrar(usuario))

    def test_administrador_tem_acesso_completo(self):
        usuario = self.criar("admin", Usuario.Perfil.ADMINISTRADOR)
        self.assertTrue(pode_administrar(usuario))
        self.assertTrue(pode_validar_analise(usuario))
        self.assertTrue(pode_executar_analise(usuario))
