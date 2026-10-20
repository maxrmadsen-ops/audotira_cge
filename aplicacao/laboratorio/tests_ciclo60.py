from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.documentos.escolhas import TipoDocumento
from aplicacao.laboratorio.classificacao import classificar_texto, segmentar_regioes
from aplicacao.laboratorio.extracao import extrair_campos, liquido_deterministico
from aplicacao.laboratorio.models import InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf, montar_relatorio, processar_lote
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


def _pdf_sintetico(quantidade: int) -> bytes:
    escritor = PdfWriter()
    for _ in range(quantidade):
        escritor.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


class TesteCiclo60Laboratorio(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo60",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(
            numero_processo="PROC-CICLO60",
            criado_por=self.usuario,
        )
        self.client.force_login(self.usuario)

    def test_catalogo_e_segmentacao_multipessa(self):
        texto = (
            "Comprovante de transferência TED valor R$ 100,00\n"
            "Demonstrativo de pagamento holerite total de proventos R$ 120,00 "
            "total de descontos R$ 20,00 líquido a receber R$ 100,00"
        )
        candidatos = classificar_texto(texto)
        tipos = {item["tipo"] for item in candidatos}
        self.assertIn("comprovante_transferencia", tipos)
        self.assertIn("holerite", tipos)
        regioes = segmentar_regioes(texto, candidatos)
        self.assertGreaterEqual(len(regioes), 2)

    def test_liquido_deterministico_e_extracao_holerite(self):
        proventos = Decimal("100.50")
        descontos = Decimal("20.25")
        self.assertEqual(liquido_deterministico(proventos, descontos), Decimal("80.25"))
        texto = (
            "Funcionário: Trabalhador Sintético\n"
            "Competência: 03/2022\n"
            "Total de proventos: R$ 100,50\n"
            "Total de descontos: R$ 20,25\n"
            "Líquido a receber: R$ 80,25\n"
            "INSS: R$ 15,00\n"
            "IRRF: R$ 5,25\n"
        )
        campos = {item["chave"]: item for item in extrair_campos("holerite", texto, 1, "nativo")}
        self.assertEqual(campos["funcionario"]["valor_original"], "Trabalhador Sintético")
        self.assertEqual(campos["total_proventos"]["valor_normalizado"], "100.50")
        self.assertEqual(campos["total_descontos"]["valor_normalizado"], "20.25")
        self.assertEqual(campos["valor_liquido"]["valor_normalizado"], "80.25")
        self.assertEqual(campos["liquido_calculado"]["valor_normalizado"], "80.25")
        self.assertTrue(campos["funcionario"]["trecho_evidencia"])

    def test_nao_preenche_campo_ausente(self):
        campos = {item["chave"]: item for item in extrair_campos("holerite", "texto insuficiente", 1, "nativo")}
        self.assertEqual(campos["funcionario"]["valor_original"], "")
        self.assertEqual(campos["funcionario"]["metodo"], "nao_localizado")

    def test_importacao_inventario_e_curadoria(self):
        with TemporaryDirectory(prefix="ciclo60-") as temporario:
            raiz = Path(temporario) / "docs"
            raiz.mkdir(parents=True, exist_ok=True)
            with override_settings(DOCUMENTOS_RAIZ=str(raiz)):
                pdf = _pdf_sintetico(3)
                caminho = raiz / "parcial-sintetica.pdf"
                caminho.write_bytes(pdf)
                lote = importar_pdf(
                    prestacao=self.prestacao,
                    caminho=caminho,
                    numero_processo_parcial="PROC-PARCIAL-60",
                    numero_instrumento="INSTR-60",
                    origem="teste-ciclo60",
                    usuario=self.usuario,
                )
                self.assertEqual(lote.hash_sha256, __import__("hashlib").sha256(pdf).hexdigest())
                self.assertEqual(lote.documento.tipo_documento, TipoDocumento.PRESTACAO_PARCIAL)
                processar_lote(lote.pk, usuario=self.usuario)
                lote.refresh_from_db()
                self.assertEqual(lote.quantidade_paginas, 3)
                self.assertEqual(InventarioPagina.objects.filter(lote=lote).count(), 3)
                # Páginas sem candidato tipado não geram peça placeholder.
                self.assertEqual(RegiaoDocumental.objects.filter(lote=lote).count(), 0)
                relatorio = montar_relatorio(lote)
                self.assertEqual(relatorio["paginas_inventariadas"], 3)
                self.assertEqual(relatorio["paginas_inconclusivas"], 3)
                self.assertEqual(relatorio["pecas_identificadas"], 0)
                resposta = self.client.get(reverse("laboratorio:processo", kwargs={"pk": self.prestacao.pk}))
                self.assertContains(resposta, "Classificação e Extração")
                self.assertContains(resposta, "PROC-PARCIAL-60")
                curadoria = self.client.get(reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}))
                self.assertContains(curadoria, "Conferência documental")
                rel = self.client.get(reverse("laboratorio:relatorio", kwargs={"lote_pk": lote.pk}))
                self.assertContains(rel, "inventário")
                detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
                self.assertContains(detalhe, "Classificação e Extração")
                self.assertContains(detalhe, "Identificação dos Envolvidos")
                self.assertContains(detalhe, "item-futuro")
