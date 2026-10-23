"""Ciclo 6.1.3: datas entre documentos, evidência derivada e localização estreita."""

from django.test import SimpleTestCase

from aplicacao.laboratorio.classificacao import dividir_dispensa_e_transferencia
from aplicacao.laboratorio.conciliacao import comparar_datas_evento
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.localizacao import caixa_na_linha
from aplicacao.laboratorio.servico import _aplicar_rubricas_na_verba


def _campos(tipo, texto):
    return {item["chave"]: item for item in extrair_campos(tipo, texto, 1, "teste")}


QUITACAO = """
TERMO DE QUITAÇÃO DE RESCISÃO DO CONTRATO DE TRABALHO
24 Data de Admissão 25 Data do Aviso Prévio 26 Data de Afastamento 27 Código Afastamento
07/03/2022 22/11/2022 21/12/2022 SJ2 0,00
no valor líquido de R$ + o qual
"""


class TesteQuitacaoEDispensa(SimpleTestCase):
    def test_afastamento_da_quitacao_nao_vira_data_da_quitacao(self):
        campos = _campos("termo_quitacao", QUITACAO)
        afastamento = campos["data_afastamento"]
        self.assertEqual(afastamento["rotulo"], "Data de Afastamento")
        self.assertEqual(afastamento["valor_original"], "21/12/2022")
        self.assertIn("Data de Afastamento", afastamento["trecho_evidencia"])
        self.assertEqual(campos["data_admissao"]["valor_original"], "07/03/2022")
        self.assertEqual(campos["data_aviso"]["valor_original"], "22/11/2022")
        self.assertEqual(campos["data"]["valor_original"], "")
        self.assertEqual(campos["data"]["rotulo"], "Data da quitação")
        self.assertEqual(campos["valor_quitado"]["valor_original"], "")

    def test_data_impossivel_nao_e_substituida_por_data_de_outro_documento(self):
        texto = """
        Comunicação de Dispensa - 7798259488
        LOCAL E DATA
        94/45/9095
        DATA DA TRANSFERENCIA 21/12/2022
        """
        campo = _campos("comunicacao_dispensa", texto)["data_comunicacao"]
        self.assertEqual(campo["valor_original"], "")
        self.assertEqual(campo["valor_normalizado"], "")
        self.assertEqual(campo["estado_confianca"], "parcial")
        self.assertIn("94/45/9095", campo["trecho_evidencia"])
        self.assertNotIn("21/12/2022", campo["valor_original"])

    def test_data_impressa_junto_do_rotulo_e_lida(self):
        texto = "Comunicação de dispensa\nLocal e data 03/01/2024"
        campo = _campos("comunicacao_dispensa", texto)["data_comunicacao"]
        self.assertEqual(campo["valor_original"], "03/01/2024")
        self.assertIn("Local e data", campo["trecho_evidencia"])

    def test_comunicacao_sem_data_permanece_vazia(self):
        campo = _campos("comunicacao_dispensa", "Comunicação de Dispensa - 123456\nNOME\nMARIA OLIVEIRA")[
            "data_comunicacao"
        ]
        self.assertEqual(campo["valor_original"], "")
        self.assertEqual(campo["estado_confianca"], "ausente")


class TesteComparacaoEEvidencia(SimpleTestCase):
    def test_datas_do_mesmo_evento_coincidem_sem_autenticar(self):
        comparado = comparar_datas_evento(
            "21/12/2022",
            "Rescisão · Data de desligamento",
            "21/12/2022",
            "Quitação · Data de Afastamento",
        )
        self.assertEqual(comparado["situacao"], "coincidente")
        self.assertIn("não autentica", comparado["detalhe"])
        self.assertNotIn("quitação comprovada", comparado["detalhe"].lower())

    def test_datas_divergentes_nao_sao_confirmadas(self):
        comparado = comparar_datas_evento("21/12/2022", "Rescisão", "22/12/2022", "Quitação")
        self.assertEqual(comparado["situacao"], "diverge")

    def test_data_ausente_nao_e_verificavel(self):
        comparado = comparar_datas_evento("21/12/2022", "Rescisão", "", "Quitação")
        self.assertEqual(comparado["situacao"], "nao_verificavel")

    def test_evidencia_derivada_usa_a_leitura_estruturada(self):
        campos = [
            {
                "chave": "verbas_rescisorias",
                "valor_original": "50 Saldo de 27/dias 1.693,97",
                "trecho_evidencia": "50 Saldo de 27/dias Salário 1.693,97",
            }
        ]
        pagina = "50 Saldo de 27/dias Salário (líquido 1.693,97"
        tabela = "50 Saldo de 21/dias Salário (líquido 1.693,97"
        _aplicar_rubricas_na_verba(campos, pagina, tabela)
        self.assertIn("21/dias", campos[0]["valor_original"])
        self.assertIn("1.693,97", campos[0]["valor_original"])
        self.assertIn("21/dias", campos[0]["trecho_evidencia"])
        self.assertNotIn("27/dias", campos[0]["trecho_evidencia"])
        self.assertIn("27/dias", pagina)

    def test_agencia_repetida_fica_na_linha_da_conta(self):
        palavras = [
            {"texto": "0685-8", "x": 0.10, "y": 0.40, "largura": 0.06, "altura": 0.012},
            {"texto": "45.320-X", "x": 0.30, "y": 0.40, "largura": 0.08, "altura": 0.012},
            {"texto": "0685-8", "x": 0.10, "y": 0.55, "largura": 0.06, "altura": 0.012},
            {"texto": "205.628-3", "x": 0.30, "y": 0.55, "largura": 0.08, "altura": 0.012},
        ]
        caixa = caixa_na_linha(palavras, "0685-8", "45.320-X")
        self.assertIsNotNone(caixa)
        self.assertLess(caixa["y"], 0.5)
        self.assertLess(caixa["largura"], 0.1)

    def test_cabecalho_do_banco_entra_na_peca_da_transferencia(self):
        palavras = [
            {"texto": "BANCO", "y": 0.64},
            {"texto": "TRANSFERENCIA", "y": 0.70},
        ]
        corte = dividir_dispensa_e_transferencia(
            "comunicação de dispensa e comprovante de transferência",
            palavras,
        )
        self.assertLess(corte, 0.64)
        self.assertGreater(corte, 0.2)
