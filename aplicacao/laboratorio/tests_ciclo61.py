"""Ciclo 6.1: conciliação sugerida, sem transformar coincidência em pagamento."""

from decimal import Decimal

from django.test import SimpleTestCase
from django.urls import reverse

from aplicacao.laboratorio.classificacao import candidatos_da_peca, classificar_texto, tipo_principal
from aplicacao.laboratorio.extracao import extrair_campos

from aplicacao.laboratorio.conciliacao import _valores_na_guia, sincronizar_cadeias
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoVinculo
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, RegiaoDocumental, VinculoEvidencia
from aplicacao.laboratorio.tests_ciclo602 import TesteCiclo602Conferencia
from aplicacao.laboratorio.vinculos import sugerir_vinculos
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, PlanoTrabalho


class TesteTipoDaAmostra(SimpleTestCase):
    def test_recolhimento_de_fgts_nao_vira_transferencia_salarial(self):
        texto = """
        COMPROVANTE DE PAGAMENTO
        Convenio FGTS ARRECADACAO
        COMPETENCIA 05/2022
        VALOR DEPOSITO 2.242,43
        GRF - GUIA DE RECOLHIMENTO DO FGTS
        """
        candidatos = classificar_texto(texto)
        principal = tipo_principal(candidatos, texto)
        self.assertEqual(principal["tipo"], "guia_fgts")
        campos = {item["chave"]: item["valor_original"] for item in extrair_campos("guia_fgts", texto, 116, "teste")}
        self.assertEqual(campos["valor_recolhimento"], "2.242,43")
        self.assertEqual(campos["competencia"], "05/2022")

    def test_rescisao_le_o_nome_depois_do_pis_sem_inventar_liquido(self):
        texto = """
        TERMO DE RESCISÃO DO CONTRATO DE TRABALHO
        02.419.958/0001-47 APAE ASSOC.DE PAIS E AMIGOS DOS EXCEP.
        11 Nome
        131.18094.72-8 LUCIANE SAURIN BIZOTO
        TOTAL BRUTO, 4.430,34
        """
        campos = {item["chave"]: item["valor_original"] for item in extrair_campos("termo_rescisao", texto, 91, "teste")}
        self.assertIn("LUCIANE SAURIN BIZOTO", campos["trabalhador"])
        self.assertIn("4.430,34", campos["total_bruto"])
        self.assertEqual(campos["total_liquido"], "")

    def test_liquido_sem_centavos_e_aviso_interno_nao_viram_pagamento(self):
        texto = """
        TERMO DE RESCISÃO DO CONTRATO DE TRABALHO
        25 Data do Aviso Prévio
        Saldo de 21/dias Salário (líquido 1.693,97
        TOTAL BRUTO 4.480,34
        VALOR LÍQUIDO | 416651
        """
        candidatos = candidatos_da_peca(classificar_texto(texto), texto)
        self.assertTrue(any(item["tipo"] == "termo_rescisao" for item in candidatos))
        self.assertFalse(any(item["tipo"] == "comunicacao_dispensa" for item in candidatos))
        campos = {item["chave"]: item["valor_original"] for item in extrair_campos("termo_rescisao", texto, 91, "teste")}
        self.assertEqual(campos["total_bruto"], "4.480,34")
        self.assertEqual(campos["total_liquido"], "")

    def test_quitacao_nao_herda_o_tipo_da_rescisao_nem_a_data_de_nascimento(self):
        texto = """
        TERMO DE QUITAÇÃO DE RESCISÃO DO CONTRATO DE TRABALHO
        02.419.958/0001-47 APAE ASSOC.DE PAIS E AMIGOS DOS EXCEP.
        11 Nome
        131.18094.72-8 LUCIANE SAURIN BIZOTO
        27/05/1981 ADELIA MILANI SAURIN
        no valor líquido de R$ + o qual
        """
        principal = tipo_principal(classificar_texto(texto), texto)
        self.assertEqual(principal["tipo"], "termo_quitacao")
        campos = {item["chave"]: item["valor_original"] for item in extrair_campos("termo_quitacao", texto, 92, "teste")}
        self.assertEqual(campos["valor_quitado"], "")
        self.assertEqual(campos["data"], "")
        self.assertIn("LUCIANE SAURIN BIZOTO", campos["trabalhador"])

    def test_encargos_da_guia_nao_usam_o_deposito_nem_o_numero_do_campo(self):
        texto = """
        COMPROVANTE DE PAGAMENTO
        Convenio FGTS ARRECADACAO GRF
        CNPJ/CEI/CPF 02419958/0001-47 É e k
        COMPETENCIA 04/2022
        VALOR DEPOSITO 2.329,85
        Data do pagamento 17/05/2022
        AUTENTICACAO SISBB: 8.F11.CBC.91A.D82.065
        14-ENCARGOS 15-TOTAL A RECOLHER
        2.207,47 122,38 2.329,85
        """
        campos = {item["chave"]: item["valor_original"] for item in extrair_campos("guia_fgts", texto, 111, "teste")}
        self.assertEqual(campos["encargos"], "122,38")
        self.assertEqual(campos["autenticacao"], "8.F11.CBC.91A.D82.065")
        self.assertEqual(campos["empregador"], "02419958/0001-47")
        self.assertNotIn("É", campos["empregador"])
        deposito, total = _valores_na_guia(texto)
        self.assertEqual(deposito, Decimal("2329.85"))
        self.assertEqual(total, Decimal("2329.85"))


class TesteConciliacao(TesteCiclo602Conferencia):
    def test_folha_confere_na_conta_e_nao_comprova_pagamento(self):
        CampoExtraido.objects.create(
            regiao=self.holerite,
            esquema="holerite",
            chave="competencia",
            rotulo="Competência",
            valor_original="03/2022",
            valor_normalizado="03/2022",
            numero_pagina=17,
            trecho_evidencia="03/2022",
            metodo="ocr_regiao",
        )
        CampoExtraido.objects.create(
            regiao=self.comprovante,
            esquema="comprovante_transferencia",
            chave="data_hora",
            rotulo="Data da transferência",
            valor_original="13/05/2022",
            valor_normalizado="13/05/2022",
            numero_pagina=17,
            trecho_evidencia="13/05/2022",
            metodo="ocr_regiao",
        )
        plano = PlanoTrabalho.objects.create(prestacao=self.prestacao, titulo="Plano", valor_global=Decimal("673370.28"))
        ItemPlanoTrabalho.objects.create(
            plano=plano,
            descricao="Pagamento de despesas com profissionais da Educação e encargos.",
            valor_previsto=Decimal("296664.71"),
            ordem=1,
        )
        sincronizar_cadeias(self.lote)
        sincronizar_cadeias(self.lote)
        cadeia = CadeiaConciliacao.objects.get(lote=self.lote, codigo=f"folha-{self.holerite.pk}")
        self.assertEqual(cadeia.estado, EstadoVinculo.SUGERIDO)
        self.assertEqual(cadeia.confianca, "sugerida")
        self.assertEqual(cadeia.comprovante_id, self.comprovante.pk)
        self.assertEqual(cadeia.separacao["comprovacao_documental"], "pendente")
        self.assertEqual(cadeia.separacao["decisao_administrativa"], "pendente")
        self.assertNotEqual(cadeia.separacao["analise_conformidade"], "confere")
        situacoes = {item["codigo"]: item for item in cadeia.verificacoes}
        self.assertEqual(situacoes["liquido_calculado"]["situacao"], "confere")
        self.assertEqual(situacoes["liquido_e_transferencia"]["situacao"], "confere")
        self.assertIn("não comprova o pagamento", situacoes["liquido_e_transferencia"]["detalhe"])
        self.assertEqual(situacoes["beneficiario"]["situacao"], "pendente")
        self.assertIn("não confirma a identidade", situacoes["beneficiario"]["detalhe"])
        self.assertEqual(situacoes["competencia_e_pagamento"]["situacao"], "nao_verificavel")
        self.assertIn("03/2022", situacoes["competencia_e_pagamento"]["detalhe"])
        self.assertIn("13/05/2022", situacoes["competencia_e_pagamento"]["detalhe"])
        self.assertEqual(situacoes["plano_trabalho"]["situacao"], "nao_verificavel")
        self.assertIn("não é o valor desta parcela", situacoes["plano_trabalho"]["detalhe"].lower())
        self.assertEqual(CadeiaConciliacao.objects.filter(lote=self.lote, codigo=cadeia.codigo).count(), 1)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.hash_sha256, self.hash_original)

    def test_nome_sem_o_mesmo_valor_nao_vira_comprovante(self):
        outra = RegiaoDocumental.objects.create(
            lote=self.lote,
            pagina=self.pagina,
            tipo_documental="comprovante_transferencia",
            ordem=3,
            metodo_deteccao="faixa_em_branco",
            texto_regiao="outra",
        )
        CampoExtraido.objects.create(
            regiao=outra,
            esquema="comprovante_transferencia",
            chave="valor",
            rotulo="Valor",
            valor_original="10,00",
            valor_normalizado="10.00",
            numero_pagina=17,
            trecho_evidencia="10,00",
            metodo="ocr_regiao",
        )
        CampoExtraido.objects.create(
            regiao=outra,
            esquema="comprovante_transferencia",
            chave="beneficiario",
            rotulo="Beneficiário",
            valor_original="LUCIANE SAURIN",
            valor_normalizado="LUCIANE SAURIN",
            numero_pagina=17,
            trecho_evidencia="LUCIANE SAURIN",
            metodo="ocr_regiao",
        )
        sincronizar_cadeias(self.lote)
        cadeia = CadeiaConciliacao.objects.get(lote=self.lote, codigo=f"folha-{self.holerite.pk}")
        self.assertEqual(cadeia.comprovante_id, self.comprovante.pk)
        sugerir_vinculos(self.lote)
        self.assertFalse(
            VinculoEvidencia.objects.filter(
                lote=self.lote,
                origem=self.holerite,
                destino=outra,
                tipo_vinculo="holerite_transferencia",
            ).exists()
        )

    def test_rescisao_sem_valor_igual_nao_usa_a_transferencia(self):
        rescisao = RegiaoDocumental.objects.create(
            lote=self.lote,
            pagina=self.pagina,
            tipo_documental="termo_rescisao",
            ordem=4,
            metodo_deteccao="faixa_em_branco",
            texto_regiao="rescisão",
        )
        CampoExtraido.objects.create(
            regiao=rescisao,
            esquema="rescisao",
            chave="trabalhador",
            rotulo="Trabalhador",
            valor_original="LUCIANE SAURIN BIZOTO",
            valor_normalizado="LUCIANE SAURIN BIZOTO",
            numero_pagina=17,
            trecho_evidencia="LUCIANE SAURIN BIZOTO",
            metodo="ocr_regiao",
        )
        sugerir_vinculos(self.lote)
        self.assertFalse(
            VinculoEvidencia.objects.filter(lote=self.lote, tipo_vinculo="rescisao_pagamento").exists()
        )
        sincronizar_cadeias(self.lote)
        cadeia = CadeiaConciliacao.objects.get(lote=self.lote, codigo=f"rescisao-{rescisao.pk}")
        self.assertIsNone(cadeia.comprovante_id)
        pagamento = next(item for item in cadeia.verificacoes if item["codigo"] == "pagamento_rescisao")
        self.assertEqual(pagamento["situacao"], "nao_verificavel")
        self.assertIn("não é irregularidade", pagamento["detalhe"])

    def test_revisao_humana_nao_confirma_o_restante(self):
        sincronizar_cadeias(self.lote)
        cadeia = CadeiaConciliacao.objects.get(lote=self.lote, codigo=f"folha-{self.holerite.pk}")
        url = reverse("laboratorio:revisar_cadeia", kwargs={"lote_pk": self.lote.pk, "cadeia_pk": cadeia.pk})
        self.client.post(url, {"acao": "rejeitar", "justificativa": ""})
        cadeia.refresh_from_db()
        self.assertEqual(cadeia.estado, EstadoVinculo.SUGERIDO)
        self.client.post(url, {"acao": "confirmar", "justificativa": ""})
        cadeia.refresh_from_db()
        self.assertEqual(cadeia.estado, EstadoVinculo.CONFIRMADO)
        liquido = self.holerite.campos.get(chave="valor_liquido")
        self.assertEqual(liquido.estado_revisao, EstadoCampo.PENDENTE)
        sincronizar_cadeias(self.lote)
        cadeia.refresh_from_db()
        self.assertEqual(cadeia.estado, EstadoVinculo.CONFIRMADO)
        resposta = self.client.get(reverse("laboratorio:conciliacao", kwargs={"lote_pk": self.lote.pk}))
        self.assertContains(resposta, "Conciliação financeira")
        self.assertContains(resposta, "Previsto")
        self.assertContains(resposta, "não comprova pagamento")
        self.assertNotContains(resposta, "pagamento comprovado")
        self.assertNotContains(resposta, "despesa elegível")
        self.lote.refresh_from_db()
        self.assertGreater(self.lote.paginas.count(), 0)
        self.assertEqual(self.lote.hash_sha256, self.hash_original)
