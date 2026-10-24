"""Ciclo 6.1.5-E: folhas novas sem repetir competência e sem transformar rescisão ilegível em obrigação."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfWriter

from aplicacao.laboratorio.classificacao import dividir_transferencia_e_holerite
from aplicacao.laboratorio.conciliacao import _cadeias_folha, _cadeias_rescisao
from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
from aplicacao.laboratorio.escolhas import EstadoCampo
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.incorporacao import (
    PAGINAS_615E,
    VERSAO_615E,
    ErroIncorporacao,
    _gravar_cadeias_novas,
    incorporar_amostra,
)
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()

HOLERITE_JUCARA = """
Demonstrativo de Pagamento de Salário
04/2022 Mensal
Nome do Funcionário CBO Empresa Local Departamento D! JUÇARA NAZARIO
PROFESSOR DE ENSINO FUNDAMENTAL Data Admissão 03/03/2022
Total 5.000,00 861,74
Total Líquido 4.138,26
"""

HOLERITE_CRISTINA = """
Demonstrativo de Pagamento de Salário
07/2022 Mensal
3 CRISTINA APARECIDA COELHO DE AVILA
Total 5.000,00 819,09
Total Líquido 4.180.91
INSS 12,00%
"""

RESCISAO_ILEGIVEL = """
TERMO DE RESCISÃO DO CONTRATO DE TRABALHO
11 Nome
CRISTINA APARECIDA COELHO DE AVILA
50 Saldo de 21/dias Salário (liquido 3.387,10
99 Ajuste do saldo devedor DOOOTALBRUTO
FOTALDEDUÇÕES 777
"""

ATESTO = """
Certifico que examinei este demonstrativo.
Nome: MARIA ROSALINA VIEIRA
CPF: 015.396.549-84
Nome do Funcionário
LUCIANE SAURIN BIZOTO
03/2022 Mensal
Total Líquido 2.221,86
"""


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class Ciclo615eTests(TestCase):
    def test_separa_trabalhador_de_cargo_percentual_e_rescisao_ilegivel(self):
        jucara = {item["chave"]: item for item in extrair_campos("holerite", HOLERITE_JUCARA, 12, "teste")}
        self.assertEqual(jucara["funcionario"]["valor_original"], "JUÇARA NAZARIO")
        self.assertNotIn("PROFESSOR", jucara["funcionario"]["valor_original"])
        self.assertEqual(jucara["competencia"]["valor_original"], "04/2022")
        self.assertEqual(jucara["valor_liquido"]["valor_normalizado"], "4138.26")
        self.assertEqual(jucara["total_proventos"]["valor_normalizado"], "5000.00")
        self.assertEqual(jucara["total_descontos"]["valor_normalizado"], "861.74")
        self.assertEqual(jucara["liquido_calculado"]["valor_normalizado"], "4138.26")
        self.assertEqual(jucara["valor_liquido"]["numero_pagina"], 12)
        cristina = {item["chave"]: item for item in extrair_campos("holerite", HOLERITE_CRISTINA, 46, "teste")}
        self.assertEqual(cristina["funcionario"]["valor_original"], "CRISTINA APARECIDA COELHO DE AVILA")
        self.assertEqual(cristina["valor_liquido"]["valor_normalizado"], "4180.91")
        self.assertNotEqual(cristina["valor_liquido"]["valor_normalizado"], "12.00")
        self.assertEqual(cristina["inss"]["valor_original"], "")
        atesto = {item["chave"]: item for item in extrair_campos("holerite", ATESTO, 17, "teste")}
        self.assertEqual(atesto["funcionario"]["valor_original"], "LUCIANE SAURIN BIZOTO")
        self.assertEqual(atesto["cpf_atesto"]["valor_original"], "015.396.549-84")
        self.assertNotIn("015.396.549-84", atesto["funcionario"]["valor_original"])
        rescisao = {item["chave"]: item for item in extrair_campos("termo_rescisao", RESCISAO_ILEGIVEL, 88, "teste")}
        self.assertEqual(rescisao["trabalhador"]["valor_original"], "CRISTINA APARECIDA COELHO DE AVILA")
        self.assertEqual(rescisao["total_liquido"]["valor_original"], "")
        self.assertEqual(rescisao["total_bruto"]["valor_original"], "")
        self.assertNotEqual(rescisao["total_liquido"]["valor_original"], "3.387,10")
        self.assertIsNone(
            dividir_transferencia_e_holerite(
                RESCISAO_ILEGIVEL,
                [{"texto": "TERMO", "y": 0.5}],
            )
        )

    def test_nao_repete_folha_nem_liga_meses_diferentes_e_mantem_pagamento_zerado(self):
        with TemporaryDirectory(prefix="ciclo615e-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                abril = self._peca(
                    lote,
                    20,
                    "holerite",
                    [
                        ("funcionario", "LUCIANE SAURIN BIZOTO", "LUCIANE SAURIN BIZOTO"),
                        ("competencia", "04/2022", "04/2022"),
                        ("valor_liquido", "2.276,20", "2276.20"),
                        ("total_proventos", "2.500,00", "2500.00"),
                        ("total_descontos", "223,80", "223.80"),
                    ],
                )
                self._peca(
                    lote,
                    20,
                    "comprovante_transferencia",
                    [("beneficiario", "LUCIANE SAURIN", "LUCIANE SAURIN"), ("valor", "2.276,20", "2276.20")],
                )
                repetida = self._peca(
                    lote,
                    28,
                    "holerite",
                    [
                        ("funcionario", "LUCIANE SAURIN BIZOTO", "LUCIANE SAURIN BIZOTO"),
                        ("competencia", "04/2022", "04/2022"),
                        ("valor_liquido", "2.276,20", "2276.20"),
                    ],
                )
                marco = self._peca(
                    lote,
                    12,
                    "holerite",
                    [
                        ("funcionario", "LUCIANE SAURIN BIZOTO", "LUCIANE SAURIN BIZOTO"),
                        ("competencia", "03/2022", "03/2022"),
                        ("valor_liquido", "2.221,86", "2221.86"),
                    ],
                )
                self._peca(
                    lote,
                    17,
                    "comprovante_transferencia",
                    [("beneficiario", "LUCIANE SAURIN", "LUCIANE SAURIN"), ("valor", "2.221,86", "2221.86")],
                )
                propostas = {item["execucao"].pk: item for item in _cadeias_folha(lote, list(lote.regioes.all()))}
                self.assertEqual(propostas[abril.pk]["comprovante"].pagina.numero_fisico, 20)
                self.assertEqual(propostas[marco.pk]["comprovante"].pagina.numero_fisico, 17)
                criadas = set(_gravar_cadeias_novas(lote))
                self.assertEqual(_gravar_cadeias_novas(lote), [])
                self.assertIn(f"folha-{marco.pk}", criadas)
                self.assertEqual(len({f"folha-{abril.pk}", f"folha-{repetida.pk}"} & criadas), 1)
                self.assertEqual(lote.cadeias.filter(codigo__startswith="folha-").count(), 2)
                rescisao = self._peca(
                    lote,
                    88,
                    "termo_rescisao",
                    [("trabalhador", "CRISTINA APARECIDA COELHO DE AVILA", "CRISTINA APARECIDA COELHO DE AVILA")],
                )
                self._peca(
                    lote,
                    90,
                    "comprovante_transferencia",
                    [("beneficiario", "CRISTINA A COELHO AVILA", "CRISTINA A COELHO AVILA"), ("valor", "7.811,51", "7811.51")],
                )
                propostas_rescisao = {item["execucao"].pk: item for item in _cadeias_rescisao(lote, list(lote.regioes.all()))}
                self.assertIsNone(propostas_rescisao[rescisao.pk]["comprovante"])
                campo = abril.campos.get(chave="valor_liquido")
                campo.estado_revisao = EstadoCampo.CONFIRMADO
                campo.save(update_fields=["estado_revisao"])
                CadeiaConciliacao.objects.filter(codigo__startswith="folha-").update(verificacoes=[{"codigo": "humana"}])
                primeira = incorporar_amostra(lote, [20], versao=VERSAO_615E)
                self.assertEqual(primeira[0]["situacao"], "ja_incorporada")
                campo.refresh_from_db()
                self.assertEqual(campo.estado_revisao, EstadoCampo.CONFIRMADO)
                self.assertEqual(
                    list(lote.cadeias.filter(codigo__startswith="folha-").values_list("verificacoes", flat=True)),
                    [[{"codigo": "humana"}], [{"codigo": "humana"}]],
                )
                self.assertNotIn(88, PAGINAS_615E)
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [88], versao=VERSAO_615E)
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [17], versao=VERSAO_615E)
                painel = montar_conferencia_integrada(lote)
                self.assertEqual(painel["executado_decimal"], Decimal("2276.20") + Decimal("2221.86"))
                self.assertEqual(painel["sugerido_decimal"], Decimal("2276.20") + Decimal("2221.86"))
                self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        usuario = Usuario.objects.create_user(
            username=f"auditor-615e-{PrestacaoContas.objects.count()}",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-615E", criado_por=usuario)
        return importar_pdf(
            prestacao=prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-ciclo615e",
            usuario=usuario,
        )

    def _pagina(self, lote, numero):
        return InventarioPagina.objects.create(lote=lote, numero_fisico=numero, quantidade_regioes=1)

    def _peca(self, lote, numero, tipo, campos):
        pagina = lote.paginas.filter(numero_fisico=numero).first() or self._pagina(lote, numero)
        regiao = RegiaoDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            tipo_documental=tipo,
            ordem=pagina.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=tipo,
            versao_extracao=VERSAO_615E,
            estado_revisao="pendente",
        )
        for chave, original, normalizado in campos:
            CampoExtraido.objects.create(
                regiao=regiao,
                esquema=tipo,
                chave=chave,
                rotulo=chave,
                valor_original=original,
                valor_normalizado=normalizado,
                numero_pagina=numero,
                trecho_evidencia=original,
                metodo="teste",
                estado_confianca="evidencia_textual" if original else "ausente",
                estado_revisao=EstadoCampo.PENDENTE if original else EstadoCampo.AUSENTE,
            )
        return regiao
