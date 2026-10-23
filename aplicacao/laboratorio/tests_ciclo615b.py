"""Ciclo 6.1.5-B: amostra financeira sem duplicar soma nem tocar páginas preservadas."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfWriter

from aplicacao.laboratorio.classificacao import (
    candidatos_da_peca,
    classificar_texto,
    dividir_transferencia_e_holerite,
    tipo_principal,
)
from aplicacao.laboratorio.conciliacao import _cadeias_darf, _cadeias_folha
from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoVinculo
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.incorporacao import ErroIncorporacao, _gravar_cadeias_novas, incorporar_amostra
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()

HOLERITE = """
COMPROVANTE DE TRANSFERENCIA
VALOR TOTAL 1.271,99
TRANSFERIDO PARA: MARCELA BORTOLINI
Demonstrativo de Pagamento de Salário
Nome do Funcionário
MARCELA BORTOLINI
02.419.958/0001-47
03/2022 Mensal
Total de proventos 1.377,81
Total de descontos 105,82
Total Líquido 1.271,99
"""

DARF = """
Documento de Arrecadação de Receitas Federais
CNPJ 02.419.958/0001-47
APAE ASSOCIACAO DE PAIS E AMIGOS DOS EXCEPCIONAIS
Código 1082
PA:04/2022
Vencimento:20/05/2022
Valor Total do Documento
2.428,92
"""

RECIBO = """
COMPROVANTE DE PAGAMENTO DE DARF/DARF SIMPLES
Banco do Brasil
DATA DO PAGAMENTO 17/05/2062
PERIODO DE APURACAO 30/04/2022
CODIGO DE RECEITA 8301
VALOR TOTAL
AUTENTICACAO SISBB: 5.9BB.15C.21B.ESC.CEO
"""

RECIBO_VALOR = """
COMPROVANTE DE PAGAMENTO DE DARF/DARF SIMPLES
Banco do Brasil
Convenio RFB-DARF
DATA DO PAGAMENTO 17/05/2022
CODIGO DE RECEITA 1082
Valor Total 2.428,92
"""


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class Ciclo615bTests(TestCase):
    def test_separa_darf_de_transferencia_e_le_o_total(self):
        tipos_guia = tipo_principal(classificar_texto(DARF), DARF)
        self.assertEqual(tipos_guia["tipo"], "darf")
        tipos_recibo = tipo_principal(classificar_texto(RECIBO), RECIBO)
        self.assertEqual(tipos_recibo["tipo"], "comprovante_darf")
        mantidos = {item["tipo"] for item in candidatos_da_peca(classificar_texto(RECIBO), RECIBO)}
        self.assertNotIn("comprovante_transferencia", mantidos)
        campos = {item["chave"]: item for item in extrair_campos("darf", DARF, 112, "teste")}
        self.assertEqual(campos["total"]["valor_normalizado"], "2428.92")
        self.assertEqual(campos["codigo_receita"]["valor_original"], "1082")
        recibo = {item["chave"]: item for item in extrair_campos("comprovante_darf", RECIBO, 110, "teste")}
        self.assertEqual(recibo["valor"]["valor_original"], "")
        self.assertEqual(recibo["data_pagamento"]["valor_original"], "17/05/2062")
        self.assertEqual(recibo["data_pagamento"]["estado_revisao"] if "estado_revisao" in recibo else "pendente", "pendente")

    def test_holerite_nao_copia_o_valor_da_transferencia_quando_o_liquido_falta(self):
        texto = """
Demonstrativo de Pagamento de Salário
Nome do Funcionário
MARCELA BORTOLINI
Total de proventos 1.377,81
Total de descontos 105,82
Total Líquido
"""
        campos = {item["chave"]: item for item in extrair_campos("holerite", texto, 50, "teste")}
        self.assertEqual(campos["valor_liquido"]["valor_original"], "")
        self.assertEqual(campos["liquido_calculado"]["valor_normalizado"], "1271.99")
        self.assertEqual(campos["liquido_calculado"]["estado_confianca"], "calculo")

    def test_corte_da_folha_usa_o_conteudo(self):
        palavras = [
            {"texto": "TRANSFERENCIA", "y": 0.2},
            {"texto": "Demonstrativo", "y": 0.62},
        ]
        self.assertEqual(dividir_transferencia_e_holerite(HOLERITE, palavras), 0.6)
        self.assertIsNone(dividir_transferencia_e_holerite("somente uma transferência bancária comum", palavras))

    def test_recusa_pagina_preservada_e_pagina_fora_da_amostra(self):
        with TemporaryDirectory(prefix="ciclo615b-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [17])
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [8])
                self.assertEqual(lote.regioes.count(), 0)

    def test_soma_obrigacao_uma_vez_e_preserva_cadeia_anterior(self):
        with TemporaryDirectory(prefix="ciclo615b-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                antiga = self._pagina(lote, 17)
                holerite = self._regiao(lote, antiga, "holerite")
                self._campo(holerite, "valor_liquido", "2.221,86", "2221.86")
                self._campo(holerite, "funcionario", "LUCIANE SAURIN BIZOTTO", "LUCIANE SAURIN BIZOTTO")
                transferencia = self._regiao(lote, antiga, "comprovante_transferencia")
                self._campo(transferencia, "valor", "2.221,86", "2221.86")
                self._campo(transferencia, "beneficiario", "LUCIANE SAURIN BIZOTTO", "LUCIANE SAURIN BIZOTTO")
                cadeia = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo=f"folha-{holerite.pk}",
                    titulo="Folha preservada",
                    execucao=holerite,
                    comprovante=transferencia,
                    estado=EstadoVinculo.SUGERIDO,
                    verificacoes=[{"codigo": "preservada", "detalhe": "não regravar"}],
                )
                nova = self._pagina(lote, 16)
                outra = self._regiao(lote, nova, "holerite", versao="6.1.5-b")
                self._campo(outra, "valor_liquido", "1.271,99", "1271.99")
                self._campo(outra, "funcionario", "MARCELA BORTOLINI", "MARCELA BORTOLINI")
                recibo = self._regiao(lote, nova, "comprovante_transferencia", versao="6.1.5-b")
                self._campo(recibo, "valor", "1.271,99", "1271.99")
                self._campo(recibo, "beneficiario", "MARCELA BORTOLINI", "MARCELA BORTOLINI")
                darf_pagina = self._pagina(lote, 112)
                darf = self._regiao(lote, darf_pagina, "darf", versao="6.1.5-b")
                self._campo(darf, "total", "2.428,92", "2428.92")
                recibo_darf_pagina = self._pagina(lote, 115)
                recibo_darf = self._regiao(lote, recibo_darf_pagina, "comprovante_darf", versao="6.1.5-b")
                self._campo(recibo_darf, "valor", "2.788,32", "2788.32")
                sem_liquido = self._pagina(lote, 50)
                parcial = self._regiao(lote, sem_liquido, "holerite", versao="6.1.5-b")
                self._campo(parcial, "liquido_calculado", "R$ 2.066,11", "2066.11")
                self._campo(parcial, "funcionario", "WALLACE SANTOS DE ARAUJO", "WALLACE SANTOS DE ARAUJO")
                transferencia_parcial = self._regiao(lote, sem_liquido, "comprovante_transferencia", versao="6.1.5-b")
                self._campo(transferencia_parcial, "valor", "2.066,11", "2066.11")
                self._campo(transferencia_parcial, "beneficiario", "WALLACE SANTOS DE ARAUJO", "WALLACE SANTOS DE ARAUJO")
                criadas = _gravar_cadeias_novas(lote)
                cadeia.refresh_from_db()
                self.assertEqual(cadeia.verificacoes, [{"codigo": "preservada", "detalhe": "não regravar"}])
                self.assertIn(f"folha-{outra.pk}", criadas)
                self.assertIn(f"darf-{darf.pk}", criadas)
                self.assertNotIn(f"folha-{holerite.pk}", criadas)
                proposta_parcial = next(item for item in _cadeias_folha(lote, list(lote.regioes.all())) if item["execucao"].pk == parcial.pk)
                self.assertEqual(proposta_parcial["comprovante"].pk, transferencia_parcial.pk)
                self.assertEqual(
                    next(item["situacao"] for item in proposta_parcial["verificacoes"] if item["codigo"] == "liquido_e_transferencia"),
                    "pendente",
                )
                propostas_darf = _cadeias_darf(lote, list(lote.regioes.all()))
                self.assertIsNone(propostas_darf[0]["comprovante"])
                painel = montar_conferencia_integrada(lote)
                self.assertEqual(painel["executado_decimal"], Decimal("5922.77"))
                self.assertEqual(painel["sugerido_decimal"], Decimal("5559.96"))
                self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
                self.assertEqual(recibo_darf.tipo_documental, "comprovante_darf")

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        usuario = Usuario.objects.create_user(
            username=f"auditor-615b-{PrestacaoContas.objects.count()}",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-615B", criado_por=usuario)
        return importar_pdf(
            prestacao=prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-ciclo615b",
            usuario=usuario,
        )

    def _pagina(self, lote, numero):
        return InventarioPagina.objects.create(lote=lote, numero_fisico=numero, quantidade_regioes=1)

    def _regiao(self, lote, pagina, tipo, versao="6.0.3"):
        return RegiaoDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            tipo_documental=tipo,
            ordem=pagina.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=tipo,
            versao_extracao=versao,
            estado_revisao="pendente",
        )

    def _campo(self, regiao, chave, original, normalizado):
        return CampoExtraido.objects.create(
            regiao=regiao,
            esquema=regiao.tipo_documental,
            chave=chave,
            rotulo=chave,
            valor_original=original,
            valor_normalizado=normalizado,
            numero_pagina=regiao.pagina.numero_fisico,
            metodo="teste",
            estado_confianca="evidencia_textual" if original else "ausente",
            estado_revisao=EstadoCampo.PENDENTE if original else EstadoCampo.AUSENTE,
        )
