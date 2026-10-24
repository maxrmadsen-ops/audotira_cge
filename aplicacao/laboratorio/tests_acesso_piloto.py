"""Controle do laboratório: flag desligada, grupo piloto e processo já autorizado."""

import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.documentos.models import Documento
from aplicacao.documentos.sinteticos import pdf_com_texto
from aplicacao.laboratorio.acesso import GRUPO_PILOTO
from aplicacao.laboratorio.models import RevisaoLaboratorio
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


def _pdf_em_branco() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


class TesteAcessoPiloto(TestCase):
    def setUp(self):
        self.auditor = Usuario.objects.create_user(
            username="auditor-piloto",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(
            numero_processo="PROC-PILOTO",
            criado_por=self.auditor,
        )
        self.url = reverse("laboratorio:processo", kwargs={"pk": self.prestacao.pk})
        self.escrita = reverse(
            "laboratorio:revisar_campo",
            kwargs={"lote_pk": 1, "campo_pk": 1},
        )
        self.client.force_login(self.auditor)

    def test_grupo_operacional_abre_e_o_restante_do_menu_permanece(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(detalhe, self.url)
        self.assertContains(detalhe, "Identificação dos Envolvidos")
        self.assertContains(detalhe, "Documentos do Processo")
        self.assertTrue(self.auditor.groups.filter(name=GRUPO_PILOTO).exists())

    def test_anonimo_e_redirecionado_sem_gravar(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.escrita).status_code, 302)
        self.assertEqual(RevisaoLaboratorio.objects.count(), 0)

    def test_autenticado_fora_do_grupo_recebe_403_e_nao_ve_o_atalho(self):
        self.auditor.groups.clear()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 403)
        detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertEqual(detalhe.status_code, 200)
        self.assertNotContains(detalhe, self.url)
        self.assertContains(detalhe, "Identificação dos Envolvidos")
        self.assertEqual(self.client.post(self.escrita).status_code, 403)
        self.assertEqual(RevisaoLaboratorio.objects.count(), 0)

    def test_consulta_no_grupo_nao_opera_o_laboratorio(self):
        consulta = Usuario.objects.create_user(
            username="consulta-piloto",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.CONSULTA,
        )
        consulta.groups.add(Group.objects.get(name=GRUPO_PILOTO))
        self.client.force_login(consulta)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.escrita).status_code, 403)

    def test_administrador_no_grupo_entra_sem_privilegio_extra(self):
        admin = Usuario.objects.create_user(
            username="admin-piloto",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ADMINISTRADOR,
        )
        self.client.force_login(admin)
        self.assertFalse(admin.is_superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    @override_settings(LABORATORIO_HABILITADO=False)
    def test_superusuario_nao_contorna_a_flag_desligada(self):
        superusuario = Usuario.objects.create_superuser(
            username="super-piloto",
            email="super-piloto@example.com",
            password="Isolada-apenas-no-teste",
        )
        superusuario.perfil = Usuario.Perfil.ADMINISTRADOR
        superusuario.save(update_fields=["perfil"])
        superusuario.groups.add(Group.objects.get_or_create(name=GRUPO_PILOTO)[0])
        self.client.force_login(superusuario)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertNotContains(detalhe, self.url)
        self.assertContains(detalhe, "Parecer")

    def test_piloto_sem_o_processo_nao_abre_o_lote_de_outro(self):
        dono = Usuario.objects.create_user(
            username="analista-dono",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        alheio = Usuario.objects.create_user(
            username="analista-alheio",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        prestacao = PrestacaoContas.objects.create(
            numero_processo="PROC-PILOTO-ALHEIO",
            criado_por=dono,
            analista_responsavel=dono,
        )
        with TemporaryDirectory(prefix="piloto-") as temporario:
            raiz = Path(temporario) / "docs"
            raiz.mkdir()
            with override_settings(DOCUMENTOS_RAIZ=str(raiz)):
                caminho = raiz / "alheio.pdf"
                caminho.write_bytes(_pdf_em_branco())
                lote = importar_pdf(
                    prestacao=prestacao,
                    caminho=caminho,
                    numero_processo_parcial="PARCIAL-ALHEIO",
                    origem="teste-piloto",
                    usuario=dono,
                )
                self.client.force_login(alheio)
                curadoria = reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk})
                resposta = self.client.get(curadoria)
                self.assertEqual(resposta.status_code, 403)
                arquivo = self.client.get(reverse("documentos:arquivo", kwargs={"pk": lote.documento_id}))
                self.assertEqual(arquivo.status_code, 403)
                self.assertFalse(arquivo.content.startswith(b"%PDF"))

    def test_revogacao_do_grupo_e_desativacao_da_conta(self):
        self.auditor.groups.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.auditor.groups.add(Group.objects.get(name=GRUPO_PILOTO))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.auditor.is_active = False
        self.auditor.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_metodo_indevido_e_csrf_nao_gravam_revisao(self):
        self.assertEqual(self.client.get(self.escrita).status_code, 405)
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.auditor)
        negado = protegido.post(self.escrita, {"acao": "confirmar"})
        self.assertEqual(negado.status_code, 403)
        self.assertEqual(RevisaoLaboratorio.objects.count(), 0)


class TestePdfContinuaProtegido(TestCase):
    def setUp(self):
        self.diretorio = TemporaryDirectory()
        self.ajuste = override_settings(DOCUMENTOS_RAIZ=self.diretorio.name)
        self.ajuste.enable()
        self.analista = Usuario.objects.create_user(
            username="analista-pdf-piloto",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        self.prestacao = PrestacaoContas.objects.create(
            numero_processo="PROC-PDF-PILOTO",
            analista_responsavel=self.analista,
            criado_por=self.analista,
        )
        self.client.force_login(self.analista)
        self.conteudo = pdf_com_texto(["Texto sintetico do controle de acesso ao arquivo."])
        self.client.post(
            reverse("documentos:enviar", kwargs={"prestacao_pk": self.prestacao.pk}),
            {"arquivos": SimpleUploadedFile("piloto.pdf", self.conteudo, content_type="application/pdf")},
        )
        self.documento = Documento.objects.get(nome_original="piloto.pdf")
        self.url = reverse("documentos:arquivo", kwargs={"pk": self.documento.pk})

    def tearDown(self):
        self.ajuste.disable()
        self.diretorio.cleanup()

    def test_intervalo_condicional_e_troca_de_usuario(self):
        faixa = self.client.get(self.url, HTTP_RANGE="bytes=0-7")
        self.assertEqual(faixa.status_code, 206)
        self.assertEqual(faixa.getvalue(), self.conteudo[:8])
        self.assertIn("private", faixa["Cache-Control"])
        self.assertIn("Cookie", faixa["Vary"])
        self.assertEqual(faixa["ETag"], f'"{self.documento.hash_sha256}"')
        self.assertEqual(hashlib.sha256(self.conteudo).hexdigest(), self.documento.hash_sha256)
        condicional = self.client.get(self.url, HTTP_IF_NONE_MATCH=faixa["ETag"])
        self.assertEqual(condicional.status_code, 304)
        self.assertIn("private", condicional["Cache-Control"])
        self.assertEqual(self.client.get(self.url, HTTP_RANGE="bytes=999999-999999").status_code, 416)
        outro = Usuario.objects.create_user(
            username="analista-pdf-outro",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        self.client.force_login(outro)
        negado = self.client.get(self.url, HTTP_IF_NONE_MATCH=faixa["ETag"], HTTP_RANGE="bytes=0-7")
        self.assertEqual(negado.status_code, 403)
        self.assertFalse(negado.content.startswith(b"%PDF"))
        self.client.logout()
        self.assertEqual(self.client.get(self.url, HTTP_RANGE="bytes=0-7").status_code, 302)

    @override_settings(LABORATORIO_HABILITADO=False)
    def test_flag_desligada_nao_bloqueia_o_pdf_do_processo_autorizado(self):
        resposta = self.client.get(self.url, HTTP_RANGE="bytes=0-7")
        self.assertEqual(resposta.status_code, 206)
        self.assertEqual(resposta.getvalue(), self.conteudo[:8])
        self.assertEqual(
            self.client.get(reverse("laboratorio:processo", kwargs={"pk": self.prestacao.pk})).status_code,
            403,
        )
