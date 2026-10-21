"""Ciclo 6.0.3: rubricas estruturadas, localização e releitura sem valor presumido."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from aplicacao.laboratorio.apresentacao import _conferir_rubricas, secoes_da_peca
from aplicacao.laboratorio.escolhas import EstadoCampo
from aplicacao.laboratorio.extracao import estruturar_rubricas, extrair_campos
from aplicacao.laboratorio.localizacao import caixa_do_valor, projetar_pagina
from aplicacao.laboratorio.models import CampoExtraido, InventarioPagina, RubricaExtraida
from aplicacao.laboratorio.releitura import (
    decidir_autenticacao,
    decidir_data,
    decidir_matricula,
    decidir_numero_impresso,
)
from aplicacao.laboratorio.tests_ciclo602 import TEXTO_COMPROVANTE, TEXTO_HOLERITE, TesteCiclo602Conferencia


class TesteRubricasELocalizacao(TestCase):
    def test_separa_percentual_e_valor_em_outro_holerite(self):
        texto = """
10 Horas Extras 012:00 hs 300,00
419 Adicional Noturno 80,00
920 IRRF 7,50 % 10,40
950 INSS 12,00 % 200,98
"""
        itens = {item["codigo"]: item for item in estruturar_rubricas(texto)}
        self.assertEqual(itens["10"]["natureza"], "provento")
        self.assertEqual(itens["10"]["referencia"], "012:00 hs")
        self.assertEqual(itens["10"]["unidade"], "hs")
        self.assertEqual(itens["10"]["valor_normalizado"], "300.00")
        self.assertEqual(itens["920"]["natureza"], "desconto")
        self.assertEqual(itens["920"]["referencia"], "7,50 %")
        self.assertEqual(itens["920"]["unidade"], "%")
        self.assertEqual(itens["920"]["valor_normalizado"], "10.40")
        self.assertNotEqual(itens["920"]["valor_normalizado"], "7.50")
        self.assertEqual(itens["950"]["valor_normalizado"], "200.98")

    def test_ruido_de_carimbo_nao_entra_na_descricao_e_permanece_na_evidencia(self):
        texto = "950 |INSS | errrrICO QuE O material: 12,00 % 200,98"
        item = estruturar_rubricas(texto)[0]
        self.assertEqual(item["descricao"], "INSS")
        self.assertIn("errrrICO", item["trecho_evidencia"])
        self.assertEqual(item["valor_original"], "200,98")

    def test_holerite_de_referencia_soma_pelos_valores_lidos(self):
        itens = estruturar_rubricas(TEXTO_HOLERITE)
        proventos = sum((Decimal(item["valor_normalizado"]) for item in itens if item["natureza"] == "provento"), Decimal("0"))
        descontos = sum((Decimal(item["valor_normalizado"]) for item in itens if item["natureza"] == "desconto"), Decimal("0"))
        self.assertEqual(proventos, Decimal("2433.24"))
        self.assertEqual(descontos, Decimal("211.38"))
        self.assertEqual(proventos - descontos, Decimal("2221.86"))

    def test_soma_inconclusiva_sem_rubrica_e_divergente_quando_difere(self):
        class Colecao:
            def __init__(self, itens):
                self.itens = itens

            def all(self):
                return self.itens

        class Rubrica:
            def __init__(self, natureza, valor):
                self.natureza = natureza
                self.valor_normalizado = valor

        class Peca:
            def __init__(self, itens):
                self.rubricas = Colecao(itens)

        vazio = _conferir_rubricas(Peca([]), Decimal("2433.24"), Decimal("211.38"))
        self.assertEqual(vazio["soma_proventos_estado"], "inconclusivo")
        divergente = _conferir_rubricas(Peca([Rubrica("provento", "10.00")]), Decimal("2433.24"), Decimal("211.38"))
        self.assertEqual(divergente["soma_proventos_estado"], "divergente")
        confere = _conferir_rubricas(
            Peca([Rubrica("provento", "2433.24"), Rubrica("desconto", "211.38")]),
            Decimal("2433.24"),
            Decimal("211.38"),
        )
        self.assertEqual(confere["soma_proventos_estado"], "confere")
        self.assertEqual(confere["soma_descontos_estado"], "confere")

    def test_localizacao_unica_e_ausencia_quando_repete(self):
        palavras = [
            {"texto": "VALOR", "x": 0.1, "y": 0.2, "largura": 0.1, "altura": 0.02},
            {"texto": "2.221,86", "x": 0.3, "y": 0.2, "largura": 0.12, "altura": 0.02},
            {"texto": "0685-8", "x": 0.1, "y": 0.3, "largura": 0.1, "altura": 0.02},
            {"texto": "0685-8", "x": 0.1, "y": 0.5, "largura": 0.1, "altura": 0.02},
        ]
        caixa = caixa_do_valor(palavras, "2.221,86")
        self.assertIsNotNone(caixa)
        self.assertAlmostEqual(caixa["x"], 0.3)
        self.assertIsNone(caixa_do_valor(palavras, "0685-8"))
        self.assertIsNone(caixa_do_valor([], "2.221,86"))
        pagina = projetar_pagina(caixa, {"x": 0.1, "y": 0.4, "largura": 0.5, "altura": 0.5})
        self.assertGreater(pagina["evidencia_x"], 0.1)
        self.assertGreater(pagina["evidencia_y"], 0.4)

    def test_documento_adicional_nao_repete_o_da_origem(self):
        campos = {item["chave"]: item for item in extrair_campos("comprovante_transferencia", TEXTO_COMPROVANTE, 17, "ocr_regiao")}
        self.assertEqual(campos["numero_documento"]["valor_original"], "550.685.000.205.628")
        self.assertEqual(campos["numero_documento_adicional"]["valor_original"], "550.685.000.045.320")
        self.assertNotEqual(campos["numero_documento"]["valor_original"], campos["numero_documento_adicional"]["valor_original"])

    def test_releitura_so_aceita_acordo_e_nao_um_valor_esperado(self):
        acordo = decidir_autenticacao("9.B3F.BFA.DDA.GDC. EDC", ["9.B3F.BFA.DDA.GDC.EDC", "codigo 9.B3F.BFA.DDA.GDC.EDC"])
        self.assertEqual(acordo["valor"], "9.B3F.BFA.DDA.GDC.EDC")
        self.assertNotIn("0DC", acordo["valor"])
        conflito = decidir_autenticacao("9.B3F.BFA.DDA.GDC. EDC", ["9.B3F.BFA.DDA.GDC.EDC", "9.B3F.BFA.DDA.0DC.EDC"])
        self.assertEqual(conflito["confianca"], "ambiguo")
        self.assertEqual(conflito["valor"], "9.B3F.BFA.DDA.GDC. EDC")
        self.assertEqual(decidir_matricula(["7", "17"])["valor"], "")
        self.assertEqual(decidir_matricula(["17", "cadastro 17"])["valor"], "17")
        self.assertIsNone(decidir_data(["sem data", "outra linha"]))
        self.assertEqual(decidir_data(["Recebi em: 4 70 19", "Recebi em 16/05/22"])["confianca"], "ambiguo")
        self.assertEqual(decidir_data(["16/05/22", "recebi 16/05/22"])["valor"], "16/05/22")
        self.assertEqual(decidir_numero_impresso(["15", "15"]), "15")
        self.assertEqual(decidir_numero_impresso(["13/05/2022", "15"]), "")
        self.assertEqual(decidir_numero_impresso(["15", "13"]), "")

    def test_rubrica_agregada_sai_da_conferencia_quando_a_estrutura_existe(self):
        class Campo:
            def __init__(self, chave):
                self.chave = chave
                self.valor_original = "texto agregado"
                self.obrigatorio = False
                self.estado_confianca = "evidencia_textual"
                self.estado_revisao = "pendente"

        campos = [
            Campo("salario_base"),
            Campo("total_proventos"),
            Campo("rubricas_proventos"),
            Campo("rubricas_descontos"),
        ]
        com_estrutura = [campo.chave for secao in secoes_da_peca("holerite", campos, rubricas_estruturadas=True) for campo in secao["campos"]]
        sem_estrutura = [campo.chave for secao in secoes_da_peca("holerite", campos, rubricas_estruturadas=False) for campo in secao["campos"]]
        self.assertIn("salario_base", com_estrutura)
        self.assertNotIn("rubricas_proventos", com_estrutura)
        self.assertNotIn("rubricas_descontos", com_estrutura)
        self.assertIn("rubricas_proventos", sem_estrutura)
        self.assertIn("rubricas_descontos", sem_estrutura)


class TesteRevisaoIndividual(TesteCiclo602Conferencia):
    def test_confirmar_uma_rubrica_nao_confirma_a_outra_nem_a_despesa(self):
        primeira = RubricaExtraida.objects.create(
            regiao=self.holerite,
            ordem=1,
            codigo="1",
            descricao="Horas Normais Diurnas",
            referencia="067:30 hs",
            unidade="hs",
            natureza="provento",
            valor_original="2.016,58",
            valor_normalizado="2016.58",
            trecho_evidencia="1 Horas Normais Diurnas 067:30 hs 2.016,58",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
        )
        segunda = RubricaExtraida.objects.create(
            regiao=self.holerite,
            ordem=2,
            codigo="419",
            descricao="Diferença Salário",
            natureza="provento",
            valor_original="416,66",
            valor_normalizado="416.66",
            trecho_evidencia="419 Diferença Salário 416,66",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
        )
        url = reverse("laboratorio:revisar_rubrica", kwargs={"lote_pk": self.lote.pk, "rubrica_pk": primeira.pk})
        self.client.post(url, {"acao": "corrigir", "descricao": "Outra", "referencia": "", "valor_original": "1,00", "justificativa": ""})
        primeira.refresh_from_db()
        self.assertEqual(primeira.estado_revisao, EstadoCampo.PENDENTE)
        self.assertEqual(primeira.valor_original, "2.016,58")
        self.client.post(
            url,
            {
                "acao": "confirmar",
                "descricao": primeira.descricao,
                "referencia": primeira.referencia,
                "valor_original": primeira.valor_original,
                "justificativa": "",
            },
        )
        primeira.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(primeira.estado_revisao, EstadoCampo.CONFIRMADO)
        self.assertEqual(segunda.estado_revisao, EstadoCampo.PENDENTE)
        liquido = CampoExtraido.objects.get(regiao=self.holerite, chave="valor_liquido")
        self.assertEqual(liquido.estado_revisao, EstadoCampo.PENDENTE)
        resposta = self.client.get(reverse("laboratorio:curadoria", kwargs={"lote_pk": self.lote.pk}) + "?pagina=17&peca=" + str(self.holerite.pk))
        self.assertContains(resposta, "Rubricas do holerite")
        self.assertContains(resposta, "Código")
        self.assertNotContains(resposta, "Rubricas de proventos")
        self.assertNotContains(resposta, "Rubricas de descontos")
        self.assertContains(resposta, "Soma das rubricas de proventos")
        self.assertContains(resposta, "Localização precisa indisponível")
        self.assertContains(resposta, "<details class=\"secao-peca\">")
        self.assertNotContains(resposta, "secao-peca\" open")
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.hash_sha256, self.hash_original)
        self.assertGreater(InventarioPagina.objects.exclude(numero_fisico=17).count(), 0)

    def test_coordenada_do_destaque_permanece_com_ponto_em_portugues(self):
        from django.utils import translation

        from aplicacao.laboratorio.templatetags.laboratorio_tags import coordenada

        self.assertEqual(coordenada(0.2123), "0.212300")
        self.assertEqual(coordenada(None), "")
        rubrica = RubricaExtraida.objects.create(
            regiao=self.holerite,
            ordem=1,
            codigo="1",
            descricao="Horas Normais Diurnas",
            natureza="provento",
            valor_original="2.016,58",
            valor_normalizado="2016.58",
            trecho_evidencia="1 Horas Normais Diurnas",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
            localizacao_precisa=True,
            evidencia_x=0.2123,
            evidencia_y=0.5912,
            evidencia_largura=0.1246,
            evidencia_altura=0.012,
        )
        with translation.override("pt-br"):
            resposta = self.client.get(
                reverse("laboratorio:curadoria", kwargs={"lote_pk": self.lote.pk})
                + "?pagina=17&peca="
                + str(rubrica.regiao_id)
            )
        self.assertContains(resposta, 'data-x="0.212300"')
        self.assertContains(resposta, 'data-w="0.124600"')
        self.assertNotContains(resposta, 'data-x="0,2123')
        self.assertNotContains(resposta, 'data-w="0,1246')
