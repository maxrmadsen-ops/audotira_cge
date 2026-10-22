"""Ciclo 6.1.2: extração tabular, data real e evidência sem virar fato comprovado."""

from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from aplicacao.laboratorio.extracao import (
    estruturar_rubricas_rescisao,
    extrair_campos,
    liquido_lido_no_texto,
    mesclar_rubricas_rescisao,
)
from aplicacao.laboratorio.localizacao import caixa_da_rubrica
from aplicacao.laboratorio.servico import _completar_traco_quitacao
from aplicacao.laboratorio.validacao import datas_rotuladas_trct, normalizar_data


TRCT = """
TERMO DE RESCISÃO DO CONTRATO DE TRABALHO
19 Data de Nascimento
27/05/1981 ADELIA MILANI SAURIN
23 Remuneração Mês Ant. 24 Data de Admissão 25 Data do Aviso Prévio 26 Data de Afastamento 27 Código Afastamento
2.500,00 07/03/2022 22/11/2022 21/12/2022 SJ2
22 Causa do Afastamento
SJ2 - Despedida sem justa causa, pelo empregador
50 Saldo de 27/dias Salário (líquido 1.693,97 51 Comissões 52 Gratificações
65 Férias Proporcionais - 10/12 avos 2.089,78
68 Terço Constitucional de Férias 696,59
112.1 Previdência Social 134,27
TOTAL BRUTO 4.480,34
TOTAL DEDUÇÕES 313,83
"""

TABELA = """
50 Saldo de 21/dias Salário (líquido 1.693,97/51 Comissões 0,00/52 Gratificações 0,00
de 0/faltas acrescidas do DSR)
65 Férias Proporcionais - 10/12 avos 2.089,78
68 Terço Constitucional de Férias 696,59
"""


def _por_chave(tipo, texto):
    return {item["chave"]: item for item in extrair_campos(tipo, texto, 1, "teste")}


def _por_codigo(itens):
    return {item["codigo"]: item for item in itens}


class TesteDatasERubricas(SimpleTestCase):
    def test_data_impossivel_nao_e_normalizada(self):
        self.assertEqual(normalizar_data("94/45/9095"), "")
        self.assertEqual(normalizar_data("04/45/9095"), "")
        self.assertEqual(normalizar_data("21/12/2022"), "21/12/2022")

    def test_afastamento_nao_copia_aviso_nem_nascimento(self):
        datas = datas_rotuladas_trct(TRCT)
        self.assertEqual(datas["data_admissao"], "07/03/2022")
        self.assertEqual(datas["data_aviso"], "22/11/2022")
        self.assertEqual(datas["data_desligamento"], "21/12/2022")
        self.assertIn("Data de Afastamento", datas["data_desligamento__evidencia"])
        self.assertNotIn("27/05/1981", datas["data_desligamento"])

    def test_so_o_aviso_nao_preenche_desligamento(self):
        texto = "24 Data de Admissão 25 Data do Aviso Prévio 26 Data de Afastamento\n22/11/2022"
        datas = datas_rotuladas_trct(texto)
        self.assertNotEqual(datas.get("data_desligamento"), "22/11/2022")

    def test_rotulo_original_permanece_e_o_campo_semantico_recebe_a_data(self):
        campos = _por_chave("termo_rescisao", TRCT)
        desligamento = campos["data_desligamento"]
        self.assertEqual(desligamento["rotulo"], "Data de desligamento")
        self.assertEqual(desligamento["valor_original"], "21/12/2022")
        self.assertIn("Data de Afastamento", desligamento["trecho_evidencia"])
        self.assertEqual(campos["total_bruto"]["valor_original"], "4.480,34")
        self.assertEqual(campos["deducoes"]["valor_original"], "313,83")
        self.assertEqual(campos["liquido_calculado"]["valor_normalizado"], "4166.51")
        self.assertEqual(campos["total_liquido"]["valor_original"], "")

    def test_tabela_corrige_a_referencia_e_preserva_o_provento(self):
        pagina = _por_codigo(estruturar_rubricas_rescisao(TRCT))
        self.assertEqual(pagina["50"]["referencia"], "27/dias")
        self.assertEqual(pagina["50"]["valor_original"], "1.693,97")
        mesclada = _por_codigo(mesclar_rubricas_rescisao(TRCT, TABELA))
        self.assertEqual(mesclada["50"]["referencia"], "21/dias")
        self.assertEqual(mesclada["50"]["unidade"], "dias")
        self.assertEqual(mesclada["50"]["valor_original"], "1.693,97")
        self.assertEqual(mesclada["50"]["valor_normalizado"], "1693.97")
        self.assertNotIn("Comissões", mesclada["50"]["descricao"])
        self.assertEqual(mesclada["51"]["valor_original"], "0,00")
        self.assertEqual(mesclada["52"]["valor_original"], "0,00")
        self.assertEqual(mesclada["65"]["referencia"], "10/12")
        self.assertEqual(mesclada["65"]["valor_original"], "2.089,78")
        self.assertEqual(mesclada["68"]["valor_original"], "696,59")
        self.assertEqual(mesclada["112.1"]["valor_original"], "134,27")
        divergente = "50 Saldo de 21/dias Salário 9.999,99"
        preservada = _por_codigo(mesclar_rubricas_rescisao(TRCT, divergente))
        self.assertEqual(preservada["50"]["valor_original"], "1.693,97")
        self.assertEqual(preservada["50"]["referencia"], "27/dias")

    def test_liquido_da_rubrica_nao_substitui_o_rodape(self):
        self.assertEqual(liquido_lido_no_texto("Salário (líquido 1.693,97"), "")
        self.assertEqual(liquido_lido_no_texto("E LÍQUIDO\n4.166,51"), "4.166,51")

    def test_leitura_diferente_nao_e_substituida_pelo_calculo(self):
        texto = "TOTAL BRUTO 4.480,34\nTOTAL DEDUÇÕES 313,83\nVALOR LÍQUIDO 4.100,00"
        campos = _por_chave("termo_rescisao", texto)
        self.assertEqual(campos["total_liquido"]["valor_original"], "4.100,00")
        self.assertEqual(campos["liquido_calculado"]["valor_normalizado"], "4166.51")
        self.assertEqual(campos["liquido_calculado"]["estado_confianca"], "calculo")


class TesteDispensaEProtocolo(SimpleTestCase):
    def test_protocolo_nao_vira_motivo_nem_data_impossivel_vira_comunicacao(self):
        texto = """
        Comunicação de Dispensa - 7798259488
        NOME
        | MARIA OLIVEIRA |
        94/45/9095
        PROTOCOLO DO EMPREGADOR
        AR
        """
        campos = _por_chave("comunicacao_dispensa", texto)
        self.assertEqual(campos["protocolo"]["valor_original"], "7798259488")
        self.assertEqual(campos["motivo"]["valor_original"], "")
        self.assertNotIn("7798259488", campos["motivo"]["valor_original"])
        self.assertEqual(campos["data_comunicacao"]["valor_original"], "")
        self.assertEqual(campos["data_comunicacao"]["valor_normalizado"], "")
        self.assertEqual(campos["data_comunicacao"]["estado_confianca"], "inconsistente")
        self.assertIn("94/45/9095", campos["data_comunicacao"]["trecho_evidencia"])
        self.assertNotEqual(campos["comprovante_recebimento"]["valor_original"], "AR")

    def test_motivo_rotulado_que_nao_e_numero_permanece(self):
        texto = "Comunicação de Dispensa - 123456\nmotivo: encerramento do contrato"
        campos = _por_chave("comunicacao_dispensa", texto)
        self.assertEqual(campos["protocolo"]["valor_original"], "123456")
        self.assertIn("encerramento", campos["motivo"]["valor_original"])


class TesteEvidenciaDaRubrica(SimpleTestCase):
    def test_codigo_unico_localiza_mesmo_com_zero_repetido(self):
        palavras = [
            {"texto": "50", "x": 0.05, "y": 0.40, "largura": 0.03, "altura": 0.02},
            {"texto": "0,00", "x": 0.40, "y": 0.40, "largura": 0.05, "altura": 0.02},
            {"texto": "51", "x": 0.50, "y": 0.40, "largura": 0.03, "altura": 0.02},
            {"texto": "0,00", "x": 0.80, "y": 0.40, "largura": 0.05, "altura": 0.02},
        ]
        caixa = caixa_da_rubrica(palavras, "50", "0,00")
        self.assertIsNotNone(caixa)
        self.assertLess(caixa["x"], 0.2)
        self.assertGreater(caixa["largura"], 0.2)

    def test_codigo_repetido_nao_inventa_coordenada(self):
        palavras = [
            {"texto": "50", "x": 0.05, "y": 0.40, "largura": 0.03, "altura": 0.02},
            {"texto": "50", "x": 0.05, "y": 0.55, "largura": 0.03, "altura": 0.02},
        ]
        self.assertIsNone(caixa_da_rubrica(palavras, "50", "1.693,97"))


class TesteAssinaturaVisual(SimpleTestCase):
    def _campos(self):
        return [
            {"chave": "assinaturas", "valor_original": "", "valor_normalizado": ""},
            {"chave": "valor_quitado", "valor_original": "", "valor_normalizado": ""},
        ]

    def test_traco_esparso_registra_presenca_sem_autenticar(self):
        imagem = Image.new("RGB", (200, 500), "white")
        desenho = ImageDraw.Draw(imagem)
        for linha in range(280, 288):
            desenho.line((30, linha, 55, linha), fill="black")
        campos = self._campos()
        _completar_traco_quitacao(
            campos,
            imagem,
            [{"texto": "Assinatura", "x": 0.1, "y": 0.50, "largura": 0.1, "altura": 0.02}],
            {"x": 0, "y": 0, "largura": 1, "altura": 1},
        )
        texto = campos[0]["valor_original"]
        self.assertIn("Traço manuscrito visível", texto)
        self.assertIn("não comprova autenticidade", texto)
        self.assertNotIn("quitação efetiva", texto.lower())
        self.assertEqual(campos[1]["valor_original"], "")
        self.assertEqual(campos[0]["estado_confianca"], "parcial")

    def test_faixa_em_branco_pede_conferencia_sem_afirmar_ausencia(self):
        imagem = Image.new("RGB", (200, 500), "white")
        campos = self._campos()
        _completar_traco_quitacao(
            campos,
            imagem,
            [{"texto": "Assinatura", "x": 0.1, "y": 0.50, "largura": 0.1, "altura": 0.02}],
            {"x": 0, "y": 0, "largura": 1, "altura": 1},
        )
        texto = campos[0]["valor_original"]
        self.assertIn("Conferência visual pendente", texto)
        self.assertNotIn("ausente", texto.lower())
        self.assertNotIn("não há assinatura", texto.lower())
        self.assertEqual(campos[1]["valor_original"], "")

    def test_quitacao_sem_valor_explicito_nao_inventa_quantia(self):
        texto = """
        TERMO DE QUITAÇÃO DE RESCISÃO DO CONTRATO DE TRABALHO
        no valor líquido de R$ + o qual
        """
        campos = _por_chave("termo_quitacao", texto)
        self.assertEqual(campos["valor_quitado"]["valor_original"], "")
        self.assertEqual(campos["assinaturas"]["valor_original"], "")
