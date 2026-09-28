import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.armazenamento import ErroArmazenamento, caminho_seguro
from aplicacao.documentos.classificacao import classificar
from aplicacao.documentos.escolhas import MetodoClassificacao, MetodoExtracao, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.metadados import _cnpj_valido, _digito
from aplicacao.documentos.models import Documento, ReprocessamentoDocumento
from aplicacao.documentos.qualidade import avaliar_qualidade
from aplicacao.documentos.sinteticos import pdf_com_texto, pdf_somente_imagem, pdf_textual_e_pagina_vazia
from aplicacao.documentos.tarefas import processar_documento_task
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()
FRASE = "Texto sintetico sem categoria reconhecivel para o classificador documental."


def cnpj_formatado() -> str:
    base = "112223330001"
    primeiro = _digito(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    segundo = _digito(base + primeiro, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    numero = base + primeiro + segundo
    return f"{numero[:2]}.{numero[2:5]}.{numero[5:8]}/{numero[8:12]}-{numero[12:]}"


class TesteDocumentos(TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.ajuste = override_settings(DOCUMENTOS_RAIZ=self.diretorio.name)
        self.ajuste.enable()
        self.analista = Usuario.objects.create_user(
            username="analista-doc",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        self.consulta = Usuario.objects.create_user(
            username="consulta-doc",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.CONSULTA,
        )
        self.administrador = Usuario.objects.create_user(
            username="admin-doc",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ADMINISTRADOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="DEMO-DOC-001", demonstracao=True)
        self.client.force_login(self.analista)

    def tearDown(self):
        self.ajuste.disable()
        self.diretorio.cleanup()

    def enviar(self, nome, conteudo, seguir=True):
        arquivo = SimpleUploadedFile(nome, conteudo, content_type="application/pdf")
        return self.client.post(
            reverse("documentos:enviar", kwargs={"prestacao_pk": self.prestacao.pk}),
            {"arquivos": arquivo},
            follow=seguir,
        )

    def test_upload_pdf_textual_hash_e_classificacao(self):
        conteudo = pdf_com_texto(
            [
                "Nota fiscal sintetica de demonstracao numero 12345.",
                "CPF 111.444.777-35 CNPJ " + cnpj_formatado() + " em 15/03/2024.",
                "Valor R$ 1.250,00. Processo nº DEMO-2024-001. Termo nº TF-DEMO-014.",
            ]
        )
        with patch("aplicacao.documentos.ocr.ServicoOCR.extrair_pagina") as ocr:
            resposta = self.enviar("nota_fiscal_sintetica.pdf", conteudo)
            ocr.assert_not_called()
        self.assertContains(resposta, "recebido")
        documento = Documento.objects.get()
        self.assertEqual(documento.hash_sha256, hashlib.sha256(conteudo).hexdigest())
        self.assertEqual(documento.tamanho_bytes, len(conteudo))
        self.assertTrue(documento.nome_armazenado.endswith(".pdf"))
        self.assertNotIn("nota_fiscal", documento.nome_armazenado)
        self.assertEqual(documento.tipo_documento, TipoDocumento.NOTA_FISCAL)
        self.assertEqual(documento.classificacao_original, TipoDocumento.NOTA_FISCAL)
        self.assertEqual(documento.status_processamento, "aguardando_validacao")
        pagina = documento.paginas.get()
        self.assertEqual(pagina.metodo_extracao, MetodoExtracao.NATIVO)
        self.assertFalse(pagina.necessitou_ocr)
        self.assertGreater(pagina.quantidade_caracteres, 40)
        cpf = documento.dados_extraidos.get(tipo="cpf")
        self.assertEqual(cpf.valor, "111.444.777-35")
        self.assertEqual(cpf.pagina_id, pagina.pk)
        self.assertIn("111.444.777-35", cpf.trecho)
        self.assertEqual(cpf.metodo, "expressao_regular")
        self.assertTrue(_cnpj_valido(cnpj_formatado()))
        self.assertTrue(documento.dados_extraidos.filter(tipo="cnpj").exists())
        self.assertTrue(documento.dados_extraidos.filter(tipo="valor_monetario").exists())
        self.assertTrue(documento.dados_extraidos.filter(tipo="numero_processo").exists())
        registro = RegistroAuditoria.objects.get(evento=RegistroAuditoria.Evento.UPLOAD)
        self.assertEqual(registro.detalhes["documento"], documento.pk)
        self.assertNotIn("111.444.777-35", str(registro.detalhes))
        arquivo = self.client.get(reverse("documentos:arquivo", kwargs={"pk": documento.pk}))
        self.assertEqual(arquivo.status_code, 200)
        self.assertTrue(arquivo.getvalue().startswith(b"%PDF"))
        self.assertContains(self.client.get(reverse("documentos:detalhe", kwargs={"pk": documento.pk})), "pdf.min.js")
        self.assertContains(self.client.get(reverse("documentos:detalhe", kwargs={"pk": documento.pk})), "Ir")

    def test_rejeita_vazio_mime_extensao_tamanho_e_pdf_corrompido(self):
        self.assertContains(self.enviar("vazio.pdf", b""), "está vazio")
        self.assertContains(self.enviar("falso.pdf", b"nao e um pdf"), "não é um PDF")
        self.assertContains(self.enviar("texto.txt", b"%PDF-1.4"), "extensão")
        with override_settings(DOCUMENTO_TAMANHO_MAXIMO_BYTES=20):
            self.assertContains(self.enviar("grande.pdf", b"%PDF" + b"x" * 40), "tamanho máximo")
        self.enviar("corrompido.pdf", b"%PDF-1.4\nconteudo invalido")
        documento = Documento.objects.get(nome_original="corrompido.pdf")
        self.assertEqual(documento.status_processamento, "erro")
        self.assertIn("PDF", documento.erro_processamento)
        self.assertTrue(RegistroAuditoria.objects.filter(evento=RegistroAuditoria.Evento.ERRO_PROCESSAMENTO).exists())

    def test_duplicidade_nao_bloqueia(self):
        conteudo = pdf_com_texto([FRASE, FRASE, FRASE])
        self.enviar("um.pdf", conteudo)
        resposta = self.enviar("dois.pdf", conteudo)
        self.assertContains(resposta, "já existe")
        self.assertEqual(Documento.objects.count(), 2)
        self.assertEqual(Documento.objects.values("hash_sha256").distinct().count(), 1)

    def test_permissao_consulta_visualiza_e_nao_envia(self):
        conteudo = pdf_com_texto([FRASE, FRASE])
        self.enviar("visivel.pdf", conteudo)
        documento = Documento.objects.get()
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse("documentos:arquivo", kwargs={"pk": documento.pk})).status_code, 200)
        self.assertEqual(self.client.get(reverse("documentos:lista")).status_code, 200)
        self.assertEqual(
            self.client.post(
                reverse("documentos:enviar", kwargs={"prestacao_pk": self.prestacao.pk}),
                {"arquivos": SimpleUploadedFile("x.pdf", conteudo, content_type="application/pdf")},
            ).status_code,
            403,
        )
        self.assertEqual(self.client.post(reverse("documentos:validar", kwargs={"pk": documento.pk}), {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("documentos:arquivo", kwargs={"pk": documento.pk})).status_code, 302)

    def test_pdf_sem_texto_aciona_ocr(self):
        conteudo = pdf_somente_imagem("RECIBO SINTETICO")
        self.enviar("recibo_imagem_sintetica.pdf", conteudo)
        documento = Documento.objects.get()
        pagina = documento.paginas.get()
        self.assertTrue(pagina.necessitou_ocr)
        self.assertTrue(pagina.ocr_executado)
        self.assertEqual(pagina.metodo_extracao, MetodoExtracao.OCR)
        self.assertIn("RECIBO", pagina.texto_extraido.upper())
        self.assertTrue(pagina.dados_posicionais.get("caixas"))
        self.assertEqual(documento.tipo_documento, TipoDocumento.RECIBO)

    def test_falha_parcial_de_ocr_nao_invalida_o_documento(self):
        conteudo = pdf_textual_e_pagina_vazia([FRASE, FRASE, FRASE])

        def ocr(self_ocr, caminho, numero):
            if numero == 2:
                raise RuntimeError("falha simulada de ocr")
            return "texto ocr", []

        with patch("aplicacao.documentos.ocr.ServicoOCR.extrair_pagina", ocr):
            self.enviar("parcial.pdf", conteudo)
        documento = Documento.objects.get()
        self.assertEqual(documento.status_processamento, "aguardando_validacao")
        self.assertEqual(documento.paginas.count(), 2)
        segunda = documento.paginas.get(numero_pagina=2)
        self.assertTrue(segunda.necessitou_ocr)
        self.assertFalse(segunda.ocr_executado)
        self.assertIn("falha simulada", segunda.erro_ocr)

    def test_nao_classificado_e_correcao_preserva_sugestao(self):
        self.enviar("sem_tipo.pdf", pdf_com_texto([FRASE, FRASE, FRASE]))
        documento = Documento.objects.get()
        self.assertEqual(documento.tipo_documento, TipoDocumento.NAO_CLASSIFICADO)
        self.assertEqual(documento.metodo_classificacao, "nenhum")
        resposta = self.client.post(
            reverse("documentos:validar", kwargs={"pk": documento.pk}),
            {"tipo_documento": TipoDocumento.OUTRO, "subtipo_documento": "anexo sintético"},
        )
        self.assertRedirects(resposta, reverse("documentos:detalhe", kwargs={"pk": documento.pk}))
        documento.refresh_from_db()
        self.assertEqual(documento.classificacao_original, TipoDocumento.NAO_CLASSIFICADO)
        self.assertEqual(documento.tipo_documento, TipoDocumento.OUTRO)
        self.assertEqual(documento.subtipo_documento, "anexo sintético")
        self.assertTrue(documento.classificacao_validada)
        self.assertEqual(documento.validado_por, self.analista)
        self.assertTrue(RegistroAuditoria.objects.filter(evento=RegistroAuditoria.Evento.RECLASSIFICACAO).exists())

    def test_celery_reprocessamento_e_painel(self):
        conteudo = pdf_com_texto([FRASE, FRASE])
        with patch("aplicacao.documentos.recebimento.processar_documento_task.delay") as atraso:
            self.enviar("fila.pdf", conteudo, seguir=False)
            atraso.assert_called_once()
        documento = Documento.objects.get()
        self.assertEqual(documento.status_processamento, "recebido")
        processar_documento_task.delay(documento.pk, self.analista.pk)
        documento.refresh_from_db()
        self.assertEqual(documento.status_processamento, "aguardando_validacao")
        self.client.post(reverse("documentos:reprocessar", kwargs={"pk": documento.pk}), {"motivo": "repetir extração"})
        self.assertEqual(ReprocessamentoDocumento.objects.get().resultado, "sucesso")
        self.assertEqual(documento.paginas.count(), 1)
        self.assertTrue(RegistroAuditoria.objects.filter(evento=RegistroAuditoria.Evento.REPROCESSAMENTO).exists())
        painel = self.client.get(reverse("documentos:lista"))
        self.assertContains(painel, "Total")
        self.assertContains(painel, "1")

    def test_arquivamento_preserva_arquivo_e_exclusao_fisica_exige_confirmacao(self):
        self.enviar("guardar.pdf", pdf_com_texto([FRASE, FRASE]))
        documento = Documento.objects.get()
        caminho = caminho_seguro(documento.nome_armazenado)
        self.client.post(reverse("documentos:arquivar", kwargs={"pk": documento.pk}))
        documento.refresh_from_db()
        self.assertIsNotNone(documento.excluido_em)
        self.assertTrue(caminho.is_file())
        self.assertNotContains(self.client.get(reverse("documentos:lista")), "guardar.pdf")
        self.client.force_login(self.administrador)
        self.client.post(reverse("documentos:excluir", kwargs={"pk": documento.pk}), {"confirmacao": "nao"})
        self.assertTrue(caminho.is_file())
        self.client.post(reverse("documentos:excluir", kwargs={"pk": documento.pk}), {"confirmacao": "EXCLUIR"})
        self.assertFalse(caminho.exists())
        self.assertFalse(Documento.objects.filter(pk=documento.pk).exists())

    def test_caminho_recusa_traversal_e_qualidade_decide_ocr(self):
        with self.assertRaises(ErroArmazenamento):
            caminho_seguro("../segredo.pdf")
        with self.assertRaises(ErroArmazenamento):
            caminho_seguro("/etc/passwd")
        qualidade, ocr = avaliar_qualidade("")
        self.assertEqual(qualidade, QualidadeExtracao.AUSENTE)
        self.assertTrue(ocr)
        qualidade, ocr = avaliar_qualidade(FRASE + " " + FRASE)
        self.assertEqual(qualidade, QualidadeExtracao.SUFICIENTE)
        self.assertFalse(ocr)
        self.assertIsInstance(Decimal("1.00"), Decimal)

    def test_aba_documentos_da_prestacao_lista_envio(self):
        self.enviar("nota_fiscal_sintetica.pdf", pdf_com_texto(["Nota fiscal sintetica de demonstracao com texto suficiente."]))
        self.client.force_login(self.consulta)
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}), {"aba": "documentos"})
        self.assertContains(resposta, "nota_fiscal_sintetica.pdf")
        self.assertContains(resposta, "Nota fiscal")


TERMO_ESTRUTURAL = """
TERMO DE FOMENTO Nº 100/2024
CONCEDENTE: Entidade Alfa.
BENEFICIÁRIO: Associação Beta do município de OUTRO/SC.
OBJETO: atendimento especializado.
CLÁUSULA PRIMEIRA — DO OBJETO.
CLÁUSULA QUINTA — DA TRANSFERÊNCIA DOS RECURSOS. montante de R$ 10,00.
A vigência encerra em 31 de dezembro de 2024.
Documento assinado digitalmente para conferencia.
O plano de trabalho segue anexo.
"""


class TesteClassificacaoEstrutural(TestCase):
    def test_estrutura_identifica_termo_e_aponta_o_trecho(self):
        resultado = classificar("anexo.pdf", TERMO_ESTRUTURAL)
        self.assertEqual(resultado["tipo"], TipoDocumento.TERMO)
        self.assertEqual(resultado["subtipo"], "Termo de Fomento")
        self.assertEqual(resultado["numero"], "100/2024")
        self.assertEqual(resultado["estado"], "identificado")
        self.assertEqual(resultado["metodo"], MetodoClassificacao.ESTRUTURAL)
        self.assertIn("TERMO DE FOMENTO Nº 100/2024", resultado["fundamento"])
        self.assertTrue(any(item["criterio"] == "título numerado do instrumento" for item in resultado["evidencias"]))
        self.assertGreaterEqual(len(resultado["evidencias"]), 3)
        colapsado = " ".join(TERMO_ESTRUTURAL.split())
        for item in resultado["evidencias"]:
            self.assertIn(item["trecho"], colapsado)

    def test_mencao_isolada_nao_vira_termo(self):
        citacao = classificar("oficio.pdf", "O ofício apenas cita o Termo de Fomento nº 100/2024, sem cláusulas nem partes.")
        mencao = classificar("relatorio.pdf", "O corpo menciona a expressão Termo de Fomento somente como referência.")
        self.assertEqual(citacao["tipo"], TipoDocumento.NAO_CLASSIFICADO)
        self.assertEqual(citacao["estado"], "insuficiente")
        self.assertEqual(mencao["tipo"], TipoDocumento.NAO_CLASSIFICADO)

    def test_titulo_sem_estrutura_nao_basta(self):
        resultado = classificar("capa.pdf", "TERMO DE FOMENTO Nº 100/2024")
        self.assertEqual(resultado["tipo"], TipoDocumento.NAO_CLASSIFICADO)

    def test_conferencia_nao_vira_nota_fiscal(self):
        resultado = classificar("assinado.pdf", "Documento assinado digitalmente para conferencia. Acesse o portal.")
        self.assertNotEqual(resultado["tipo"], TipoDocumento.NOTA_FISCAL)
        self.assertEqual(resultado["tipo"], TipoDocumento.NAO_CLASSIFICADO)

    def test_indicios_concorrentes_nao_desempatam(self):
        resultado = classificar("misto.pdf", "Recibo de declaracao sintetica sem outro contexto.")
        self.assertEqual(resultado["tipo"], TipoDocumento.NAO_CLASSIFICADO)
        self.assertGreaterEqual(len(resultado["evidencias"]), 2)

    def test_regra_nao_conhece_o_caso_piloto(self):
        fonte = Path(__file__).with_name("classificacao.py").read_text(encoding="utf-8")
        self.assertNotIn("929", fonte)
        self.assertNotIn("VARGEM", fonte)
        self.assertNotIn("345.284", fonte)
