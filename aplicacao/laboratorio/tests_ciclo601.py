from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.laboratorio.classificacao import classificar_texto, segmentar_regioes
from aplicacao.laboratorio.escolhas import EstadoClassificacao
from aplicacao.laboratorio.extracao import extrair_campos, liquido_deterministico
from aplicacao.laboratorio.models import InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf, montar_relatorio, processar_lote
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


def _pdf(n: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(n):
        writer.add_blank_page(width=595, height=842)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TesteCiclo601(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo601",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(
            numero_processo="PROC-CICLO601",
            criado_por=self.usuario,
        )
        self.client.force_login(self.usuario)

    def test_menu_jornada_auditor(self):
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "Gestão")
        self.assertContains(resposta, "Etapa de Preparação")
        self.assertContains(resposta, "Etapa de Execução")
        self.assertContains(resposta, "Identificação dos Envolvidos")
        self.assertContains(resposta, "Documentos do Processo")
        self.assertContains(resposta, "Classificação e Extração")
        self.assertNotContains(resposta, "Laboratório documental")

    def test_identificacao_distinguie_cadastro_e_extracao(self):
        resposta = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(resposta, "Identificação dos envolvidos")
        self.assertContains(resposta, "Concedente (cadastro)")
        self.assertContains(resposta, "Beneficiário (extraído do termo)")
        self.assertContains(resposta, "Valores do Plano de Trabalho")
        self.assertContains(resposta, "Distribuição do processo")

    def test_placeholder_nao_conta_como_peca(self):
        texto = "página administrativa sem tipo tipado suficiente"
        self.assertEqual(segmentar_regioes(texto, classificar_texto(texto)), [])
        texto2 = (
            "Comprovante de transferência TED\n"
            "Demonstrativo de pagamento holerite líquido a receber R$ 100,00"
        )
        regioes = segmentar_regioes(texto2, classificar_texto(texto2))
        self.assertGreaterEqual(len(regioes), 2)
        self.assertEqual(regioes[0]["tipo"], "comprovante_transferencia")
        self.assertEqual(regioes[1]["tipo"], "holerite")

    def test_campos_holerite_com_evidencia(self):
        texto = (
            "Nome do empregado: Trabalhador Exemplo Silva\n"
            "Competência: 03/2022\n"
            "Total de proventos: R$ 100,50\n"
            "Total de descontos: R$ 20,25\n"
            "Líquido a receber: R$ 80,25\n"
            "INSS R$ 15,00\n"
            "IRRF R$ 5,25\n"
        )
        campos = {c["chave"]: c for c in extrair_campos("holerite", texto, 17, "ocr")}
        self.assertIn("Trabalhador", campos["funcionario"]["valor_original"])
        self.assertEqual(campos["valor_liquido"]["valor_normalizado"], "80.25")
        self.assertEqual(liquido_deterministico(Decimal("100.50"), Decimal("20.25")), Decimal("80.25"))
        self.assertEqual(campos["liquido_calculado"]["valor_normalizado"], "80.25")

    def test_inventario_e_conferencia_sem_titulo_generico(self):
        with TemporaryDirectory(prefix="ciclo601-") as tmp:
            raiz = Path(tmp) / "docs"
            raiz.mkdir()
            with override_settings(DOCUMENTOS_RAIZ=str(raiz)):
                caminho = raiz / "Processo SCC 00004208_2023 - parcial 01.pdf"
                caminho.write_bytes(_pdf(2))
                lote = importar_pdf(
                    prestacao=self.prestacao,
                    caminho=caminho,
                    numero_processo_parcial="SCC-TEST-601",
                    numero_instrumento="INSTR-601",
                    usuario=self.usuario,
                )
                processar_lote(lote.pk, usuario=self.usuario)
                self.assertEqual(lote.documento.nome_original, "Processo SCC 00004208_2023 - parcial 01.pdf")
                rel = montar_relatorio(lote)
                self.assertEqual(rel["paginas_inventariadas"], 2)
                self.assertEqual(rel["pecas_identificadas"], 0)
                self.assertEqual(rel["paginas_inconclusivas"], 2)
                self.assertIn("não equivale", rel["aviso_inventario"].lower())
                inventario = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}))
                self.assertContains(inventario, "Processo SCC 00004208_2023 - parcial 01.pdf")
                self.assertContains(inventario, "Sem classificação conclusiva")
                self.assertContains(inventario, "Filtros")
                conf = self.client.get(reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}), {"pagina": 1})
                self.assertContains(conf, "Conferência documental")
                self.assertContains(conf, "Peças identificadas")
                self.assertNotContains(conf, "Título observado: 9")
                docs = self.client.get(
                    reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
                    {"aba": "documentos"},
                )
                self.assertContains(docs, "Abrir inventário")
                self.assertContains(docs, "Classificação e Extração")
