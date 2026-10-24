"""Ciclo 6.1.5-F: rescisões só entram na soma quando bruto, deduções e líquido fecham."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfWriter

from aplicacao.laboratorio.classificacao import dividir_dispensa_e_transferencia
from aplicacao.laboratorio.conciliacao import _nome_proximo
from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoVinculo
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.incorporacao import (
    PAGINAS_615E,
    PAGINAS_615F,
    VERSAO_615F,
    ErroIncorporacao,
    _gravar_cadeias_novas,
    _totais_rescisao_conferem,
    incorporar_amostra,
)
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import _completar_totais_trct, _valor_apos_rotulo, importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class Ciclo615fTests(TestCase):
    def test_rotulo_separa_total_de_zero_e_de_percentual(self):
        self.assertEqual(_valor_apos_rotulo("0,00 TOTAL BRUTO FER 8.942,66", "bruto"), "8.942,66")
        self.assertEqual(_valor_apos_rotulo("OTAL DEDUÇÕES 1.131,15", "dedu"), "1.131,15")
        self.assertEqual(_valor_apos_rotulo("VALOR LÍQUIDO au 7.811,51", "quido"), "7.811,51")
        self.assertEqual(_valor_apos_rotulo("DEDUÇÕES 12,00% 1.140,64", "dedu"), "1.140,64")
        self.assertEqual(_valor_apos_rotulo("TOTAL BRUTO", "bruto"), "")

    def test_conta_quebrada_nao_autoriza_obrigacao(self):
        texto = """
        50 Saldo de 21/dias Salário (liquido 3.387,10)
        TOTAL BRUTO 8.942,66
        TOTAL DEDUÇÕES 1.131,15
        VALOR LÍQUIDO 781,51
        """
        campos = {item["chave"]: item for item in extrair_campos("termo_rescisao", texto, 88, "teste")}
        self.assertEqual(campos["total_liquido"]["valor_original"], "781,51")
        self.assertNotEqual(campos["total_liquido"]["valor_original"], "7.811,51")
        self.assertNotEqual(campos["total_liquido"]["valor_original"], "3.387,10")

    def test_faixa_ausente_nao_inventa_totais(self):
        campos = [
            {"chave": "total_bruto", "valor_original": "", "metodo": "ocr_regiao"},
            {"chave": "deducoes", "valor_original": "", "metodo": "ocr_regiao"},
            {"chave": "total_liquido", "valor_original": "", "metodo": "ocr_regiao"},
        ]
        _completar_totais_trct(campos, "caminho-inexistente.pdf", 88)
        self.assertEqual([campo["valor_original"] for campo in campos], ["", "", ""])

    def test_transferencia_no_topo_separa_a_dispensa_de_baixo(self):
        corte = dividir_dispensa_e_transferencia(
            "comprovante de transferência e comunicação de dispensa",
            [{"texto": "TRANSFERENCIA", "y": 0.16}, {"texto": "DISPENSA", "y": 0.58}],
        )
        self.assertAlmostEqual(corte, 0.56, places=2)
        preservado = dividir_dispensa_e_transferencia(
            "comunicação de dispensa e comprovante de transferência",
            [{"texto": "BANCO", "y": 0.64}, {"texto": "TRANSFERENCIA", "y": 0.70}],
        )
        self.assertLess(preservado, 0.64)
        self.assertGreater(preservado, 0.2)

    def test_nomes_de_cristina_e_jucara_nao_atingem_luciane(self):
        self.assertTrue(_nome_proximo("CRISTINA APARECIDA COELHO DE AVILA", "CRISTINA A COELHO AVILA"))
        self.assertTrue(_nome_proximo("JUÇARA NAZARIO", "JUCARA NAZARIO"))
        self.assertFalse(_nome_proximo("CRISTINA APARECIDA COELHO DE AVILA", "LUCIANE SAURIN BIZOTO"))
        self.assertFalse(_nome_proximo("JUÇARA NAZARIO", "LUCIANE SAURIN"))
        self.assertTrue(_nome_proximo("LUCIANE SAURIN", "LUCIANE SAURIN BIZOTO"))

    def test_duas_rescisoes_entram_sem_repetir_salario_nem_confirmar_pagamento(self):
        with TemporaryDirectory() as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                cristina = self._peca(
                    lote,
                    88,
                    "termo_rescisao",
                    [
                        ("trabalhador", "CRISTINA APARECIDA COELHO DE AVILA", "CRISTINA APARECIDA COELHO DE AVILA"),
                        ("data_desligamento", "21/12/2022", "21/12/2022"),
                        ("total_bruto", "8.942,66", "8942.66"),
                        ("deducoes", "1.131,15", "1131.15"),
                        ("total_liquido", "7.811,51", "7811.51"),
                    ],
                )
                self._peca(
                    lote,
                    89,
                    "termo_rescisao",
                    [
                        ("trabalhador", "CRISTINA APARECIDA COELHO DE AVILA", "CRISTINA APARECIDA COELHO DE AVILA"),
                        ("data_desligamento", "21/12/2022", "21/12/2022"),
                        ("total_bruto", "8.942,66", "8942.66"),
                        ("deducoes", "1.131,15", "1131.15"),
                        ("total_liquido", "7.811,51", "7811.51"),
                    ],
                )
                self._peca(lote, 89, "termo_quitacao", [("trabalhador", "CRISTINA APARECIDA COELHO DE AVILA", "CRISTINA APARECIDA COELHO DE AVILA")])
                recibo_cristina = self._peca(
                    lote,
                    90,
                    "comprovante_transferencia",
                    [("beneficiario", "CRISTINA A COELHO AVILA", "CRISTINA A COELHO AVILA"), ("valor", "7.811,51", "7811.51")],
                )
                jucara = self._peca(
                    lote,
                    94,
                    "termo_rescisao",
                    [
                        ("trabalhador", "JUÇARA NAZARIO", "JUÇARA NAZARIO"),
                        ("data_desligamento", "21/12/2022", "21/12/2022"),
                        ("total_bruto", "8.942,66", "8942.66"),
                        ("deducoes", "1.140,64", "1140.64"),
                        ("total_liquido", "7.802,02", "7802.02"),
                    ],
                )
                recibo_jucara = self._peca(
                    lote,
                    96,
                    "comprovante_transferencia",
                    [("beneficiario", "JUCARA NAZARIO", "JUCARA NAZARIO"), ("valor", "7.802,02", "7802.02")],
                )
                incompleta = self._peca(
                    lote,
                    95,
                    "termo_rescisao",
                    [
                        ("trabalhador", "CRISTINA APARECIDA COELHO DE AVILA", "CRISTINA APARECIDA COELHO DE AVILA"),
                        ("total_bruto", "8.942,66", "8942.66"),
                        ("deducoes", "1.131,15", "1131.15"),
                        ("total_liquido", "781,51", "781.51"),
                    ],
                )
                self.assertFalse(_totais_rescisao_conferem(incompleta))
                self.assertTrue(_totais_rescisao_conferem(cristina))
                folha = self._peca(
                    lote,
                    12,
                    "holerite",
                    [
                        ("funcionario", "JUÇARA NAZARIO", "JUÇARA NAZARIO"),
                        ("competencia", "04/2022", "04/2022"),
                        ("valor_liquido", "4.138,26", "4138.26"),
                    ],
                )
                salario = self._peca(
                    lote,
                    12,
                    "comprovante_transferencia",
                    [("beneficiario", "JUCARA NAZARIO", "JUCARA NAZARIO"), ("valor", "4.138,26", "4138.26")],
                )
                luciane = self._peca(
                    lote,
                    91,
                    "termo_rescisao",
                    [
                        ("trabalhador", "LUCIANE SAURIN BIZOTO", "LUCIANE SAURIN BIZOTO"),
                        ("data_desligamento", "21/12/2022", "21/12/2022"),
                        ("total_bruto", "4.480,34", "4480.34"),
                        ("deducoes", "313,83", "313.83"),
                        ("total_liquido", "4.166,51", "4166.51"),
                    ],
                )
                decidida = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo="rescisao-preservada",
                    titulo="Decisão humana",
                    execucao=luciane,
                    estado=EstadoVinculo.CONFIRMADO,
                    verificacoes=[{"codigo": "humana"}],
                )
                criadas = _gravar_cadeias_novas(lote)
                self.assertEqual(_gravar_cadeias_novas(lote), [])
                self.assertEqual(len([codigo for codigo in criadas if codigo.startswith("rescisao-")]), 2)
                self.assertNotIn(f"rescisao-{incompleta.pk}", criadas)
                self.assertNotIn(f"rescisao-{luciane.pk}", criadas)
                cadeias = list(
                    lote.cadeias.filter(codigo__startswith="rescisao-").exclude(codigo="rescisao-preservada")
                )
                self.assertEqual(len(cadeias), 2)
                por_valor = {
                    cadeia.execucao.campos.get(chave="total_liquido").valor_normalizado: cadeia for cadeia in cadeias
                }
                self.assertEqual(por_valor["7811.51"].comprovante_id, recibo_cristina.pk)
                self.assertEqual(por_valor["7802.02"].comprovante_id, recibo_jucara.pk)
                self.assertEqual(por_valor["7811.51"].estado, EstadoVinculo.SUGERIDO)
                self.assertIsNone(por_valor["7811.51"].revisado_por)
                self.assertNotEqual(por_valor["7802.02"].comprovante_id, salario.pk)
                self.assertNotEqual(por_valor["7802.02"].execucao_id, folha.pk)
                decidida.refresh_from_db()
                self.assertEqual(decidida.estado, EstadoVinculo.CONFIRMADO)
                self.assertEqual(decidida.verificacoes, [{"codigo": "humana"}])
                painel = montar_conferencia_integrada(lote)
                self.assertEqual(
                    painel["executado_decimal"],
                    Decimal("7811.51") + Decimal("7802.02") + Decimal("4138.26") + Decimal("4166.51"),
                )
                self.assertEqual(painel["sugerido_decimal"], Decimal("7811.51") + Decimal("7802.02") + Decimal("4138.26"))
                self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
                self.assertNotIn(88, PAGINAS_615E)
                self.assertEqual(PAGINAS_615F, (88, 89, 90, 94, 95, 96))
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [91], versao=VERSAO_615F)
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [99], versao=VERSAO_615F)
                pagina = lote.paginas.get(numero_fisico=88)
                campo = cristina.campos.get(chave="total_liquido")
                campo.estado_revisao = EstadoCampo.CONFIRMADO
                campo.save(update_fields=["estado_revisao"])
                pagina.regioes.update(versao_extracao=VERSAO_615F)
                relatorio = incorporar_amostra(lote, [88], versao=VERSAO_615F)
                self.assertEqual(relatorio[0]["situacao"], "ja_incorporada")
                campo.refresh_from_db()
                self.assertEqual(campo.estado_revisao, EstadoCampo.CONFIRMADO)

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        usuario = Usuario.objects.create_user(
            username=f"auditor-615f-{PrestacaoContas.objects.count()}",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-615F", criado_por=usuario)
        return importar_pdf(
            prestacao=prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-ciclo615f",
            usuario=usuario,
        )

    def _peca(self, lote, numero, tipo, campos):
        pagina = lote.paginas.filter(numero_fisico=numero).first()
        if pagina is None:
            pagina = InventarioPagina.objects.create(lote=lote, numero_fisico=numero, quantidade_regioes=1)
        regiao = RegiaoDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            tipo_documental=tipo,
            ordem=pagina.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=tipo,
            versao_extracao="teste",
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
                estado_confianca="evidencia_textual",
                estado_revisao=EstadoCampo.PENDENTE,
            )
        return regiao
