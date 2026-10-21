from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.laboratorio.apresentacao import comparar_pagina, rotulo_metodo
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoClassificacao, EstadoRevisao
from aplicacao.laboratorio.extracao import extrair_campos, liquido_deterministico
from aplicacao.laboratorio.models import CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.segmentacao import faixas_por_densidade
from aplicacao.laboratorio.servico import importar_pdf, processar_lote
from aplicacao.prestacoes_contas.identificacao import montar_identificacao
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()

TEXTO_COMPROVANTE = """
13/05/22, 16:27 Banco do Brasil
13/05/2022 - BANCO DO BRASIL - 15:49:52
COMPROVANTE DE TRANSFERENCIA
DE CONTA CORRENTE P/ CONTA CORRENTE
CLIENTE: APAE MRD
AGENCIA: 0685-8 CONTA: 45.320-X
NR. DOCUMENTO 550.685.000.205.628
DATA DA TRANSFERENCIA 13/05/2022
VALOR TOTAL 2.221,86
TRANSFERIDO PARA:
CLIENTE: LUCIANE SAURIN
AGENCIA: 0685-8 CONTA: 205.628-3
NR. DOCUMENTO 550.685.000.045.320
NR. AUTENTICACAO 9.B3F.BFA.DDA.0DC.EDC
"""

TEXTO_HOLERITE = """
APAE ASSOC. DE PAIS E AMIGOS DOS EXCEP. Demonstrativo de Pagamento de Salário
CNPJ 02.419.958/0001-47
03/2022 Mensal
Cadastro
17 LUCIANE SAURIN BIZOTO
CBO 3331
Professor
Data Admissão 07/03/2022
1 Horas Normais Diurnas 067:30 hs 2.016,58
419 Diferença Salário 416,66
920 IRRF 7,50 % 10,40
950 INSS 12,00 % 200,98
Total 2.433,24 211,38
Salário Base 2.500,00
Sal Cont INSS 2.433,24
Bas Calc FGTS 2.433,24
FGTS Mês 194,65
Bas Cálc IRRF 2.232,26
Total Líquido 2.221,86
Recebi em: 16/05/22
Assinatura
CERTIFICO QUE O MATERIAL FOI PRESTADO
NOME: Maria Rosalina Vieira
CARGO: Presidente
CPF:015.396.549-84
"""


def _pdf_sintetico() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


class TesteCiclo602Extracao(TestCase):
    def test_faixa_em_branco_nao_divide_ao_meio(self):
        densidades = [0.0] * 20 + [0.05] * 30 + [0.0] * 40 + [0.08] * 80 + [0.0] * 10
        faixas = faixas_por_densidade(densidades)
        self.assertEqual(len(faixas), 2)
        self.assertLess(faixas[0]["y"] + faixas[0]["altura"], 0.4)
        self.assertGreater(faixas[1]["y"], 0.4)
        self.assertNotEqual(round(faixas[0]["altura"], 2), round(faixas[1]["altura"], 2))

    def test_espaco_interno_nao_vira_outra_peca(self):
        densidades = [0.0] * 1000
        for indice in list(range(0, 200)) + list(range(220, 500)) + list(range(580, 900)):
            densidades[indice] = 0.05
        self.assertEqual(len(faixas_por_densidade(densidades)), 2)
        self.assertEqual(faixas_por_densidade([]), [])

    def test_comprovante_separa_data_hora_documento_e_autenticacao(self):
        campos = {item["chave"]: item for item in extrair_campos("comprovante_transferencia", TEXTO_COMPROVANTE, 17, "ocr_regiao")}
        self.assertEqual(campos["instituicao"]["valor_original"], "Banco do Brasil")
        self.assertEqual(campos["titular_origem"]["valor_original"], "APAE MRD")
        self.assertEqual(campos["beneficiario"]["valor_original"], "LUCIANE SAURIN")
        self.assertEqual(campos["agencia_origem"]["valor_original"], "0685-8")
        self.assertEqual(campos["conta_origem"]["valor_original"], "45.320-X")
        self.assertEqual(campos["conta_destino"]["valor_original"], "205.628-3")
        self.assertEqual(campos["data_hora"]["valor_original"], "13/05/2022")
        self.assertEqual(campos["hora_operacao"]["valor_original"], "15:49:52")
        self.assertIn("16:27", campos["data_hora_impressao"]["valor_original"])
        self.assertNotIn("16:27", campos["data_hora"]["valor_original"])
        self.assertNotIn("15:49:52", campos["data_hora_impressao"]["valor_original"])
        self.assertEqual(campos["valor"]["valor_normalizado"], "2221.86")
        self.assertEqual(campos["numero_documento"]["valor_original"], "550.685.000.205.628")
        self.assertEqual(campos["autenticacao"]["valor_original"], "9.B3F.BFA.DDA.0DC.EDC")
        self.assertNotEqual(campos["autenticacao"]["valor_original"], campos["numero_documento"]["valor_original"])
        self.assertNotIn("IDO", campos["beneficiario"]["trecho_evidencia"])
        self.assertIn("LUCIANE SAURIN", campos["beneficiario"]["trecho_evidencia"])

    def test_holerite_nao_mistura_empregador_cpf_e_totais(self):
        campos = {item["chave"]: item for item in extrair_campos("holerite", TEXTO_HOLERITE, 17, "ocr_regiao")}
        self.assertEqual(campos["empregador"]["valor_original"], "APAE ASSOC. DE PAIS E AMIGOS DOS EXCEP.")
        self.assertNotIn("Demonstrativ", campos["empregador"]["valor_original"])
        self.assertNotIn("Demonstrativ", campos["empregador"]["trecho_evidencia"])
        self.assertEqual(campos["funcionario"]["valor_original"], "LUCIANE SAURIN BIZOTO")
        self.assertNotIn("015.396.549-84", campos["funcionario"]["valor_original"])
        self.assertNotIn("015.396.549-84", campos["identificadores"]["valor_original"])
        self.assertEqual(campos["cpf_atesto"]["valor_original"], "015.396.549-84")
        self.assertIn("Maria Rosalina Vieira", campos["responsavel_atesto"]["valor_original"])
        self.assertEqual(campos["matricula"]["valor_original"], "17")
        self.assertEqual(campos["cbo"]["valor_original"], "3331")
        self.assertEqual(campos["competencia"]["valor_original"], "03/2022")
        self.assertNotEqual(campos["competencia"]["valor_original"], "07/03/2022")
        self.assertEqual(campos["data_admissao"]["valor_original"], "07/03/2022")
        self.assertEqual(campos["salario_base"]["valor_normalizado"], "2500.00")
        self.assertEqual(campos["total_proventos"]["valor_normalizado"], "2433.24")
        self.assertEqual(campos["total_descontos"]["valor_normalizado"], "211.38")
        self.assertEqual(campos["valor_liquido"]["valor_normalizado"], "2221.86")
        self.assertEqual(campos["inss"]["valor_normalizado"], "200.98")
        self.assertEqual(campos["irrf"]["valor_normalizado"], "10.40")
        self.assertEqual(campos["fgts_mes"]["valor_normalizado"], "194.65")
        self.assertEqual(campos["base_irrf"]["valor_normalizado"], "2232.26")
        self.assertIn("Horas Normais Diurnas", campos["rubricas_proventos"]["valor_original"])
        self.assertIn("2.016,58", campos["rubricas_proventos"]["valor_original"])
        self.assertIn("INSS", campos["rubricas_descontos"]["valor_original"])
        self.assertIn("200,98", campos["rubricas_descontos"]["valor_original"])
        self.assertNotIn("Maria Rosalina", campos["rubricas_descontos"]["valor_original"])
        self.assertEqual(
            liquido_deterministico(Decimal("2433.24"), Decimal("211.38")),
            Decimal("2221.86"),
        )
        self.assertEqual(campos["liquido_calculado"]["valor_normalizado"], "2221.86")
        self.assertEqual(campos["funcionario"]["trecho_evidencia"], "17 LUCIANE SAURIN BIZOTO")

    def test_cbo_na_linha_seguinte_nao_grava_matricula_ilegivel(self):
        texto = """
Zadastro Nome do Funcionário CBO Empresa Local Departamento FL
7 LUCIANE SAURIN BIZOTO 3331 540, 1 001.001 01
Recebi em: 4 70 19 S Assinatura
"""
        campos = {item["chave"]: item for item in extrair_campos("holerite", texto, 17, "ocr_regiao")}
        self.assertEqual(campos["cbo"]["valor_original"], "3331")
        self.assertEqual(campos["matricula"]["valor_original"], "")
        self.assertEqual(campos["data_recebimento"]["valor_original"], "")

    def test_rotulo_amigavel_nao_declara_segmentacao_validada(self):
        self.assertEqual(
            rotulo_metodo("faixa_em_branco", EstadoClassificacao.PROPOSTO),
            "Separação automática preliminar — revisão pendente",
        )
        self.assertEqual(
            rotulo_metodo("segmentacao_heuristica_multipessa", ""),
            "Separação automática preliminar — revisão pendente",
        )
        self.assertIn("revisão pendente", rotulo_metodo("ajuste_humano", EstadoClassificacao.PROPOSTO))


class TesteCiclo602Conferencia(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo602",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(
            numero_processo="SCC 3350/2022",
            criado_por=self.usuario,
        )
        self.client.force_login(self.usuario)
        with TemporaryDirectory(prefix="ciclo602-") as temporario:
            raiz = Path(temporario) / "docs"
            raiz.mkdir(parents=True, exist_ok=True)
            with override_settings(DOCUMENTOS_RAIZ=str(raiz)):
                pdf = _pdf_sintetico()
                caminho = raiz / "Processo SCC 00004208_2023 - parcial 01.pdf"
                caminho.write_bytes(pdf)
                self.lote = importar_pdf(
                    prestacao=self.prestacao,
                    caminho=caminho,
                    numero_processo_parcial="SCC 00004208/2023",
                    numero_instrumento="2022TR000929",
                    origem="teste-ciclo602",
                    usuario=self.usuario,
                )
                self.hash_original = self.lote.hash_sha256
                processar_lote(self.lote.pk, usuario=self.usuario)
        self.pagina = InventarioPagina.objects.create(
            lote=self.lote,
            numero_fisico=17,
            numero_impresso="15",
            tipos_candidatos=["comprovante_transferencia", "holerite"],
            quantidade_regioes=2,
            estado_classificacao=EstadoClassificacao.PROPOSTO,
            estado_revisao=EstadoRevisao.PENDENTE,
        )
        self.comprovante = RegiaoDocumental.objects.create(
            lote=self.lote,
            pagina=self.pagina,
            tipo_documental="comprovante_transferencia",
            ordem=1,
            y=0.02,
            altura=0.36,
            metodo_deteccao="faixa_em_branco",
            versao_extracao="6.0.2",
            estado_classificacao=EstadoClassificacao.PROPOSTO,
            texto_regiao="LUCIANE SAURIN",
        )
        self.holerite = RegiaoDocumental.objects.create(
            lote=self.lote,
            pagina=self.pagina,
            tipo_documental="holerite",
            ordem=2,
            y=0.46,
            altura=0.48,
            metodo_deteccao="faixa_em_branco",
            versao_extracao="6.0.2",
            estado_classificacao=EstadoClassificacao.PROPOSTO,
            texto_regiao="LUCIANE SAURIN BIZOTO",
        )
        CampoExtraido.objects.create(
            regiao=self.comprovante,
            esquema="comprovante_transferencia",
            chave="valor",
            rotulo="Valor",
            valor_original="2.221,86",
            valor_normalizado="2221.86",
            numero_pagina=17,
            trecho_evidencia="VALOR TOTAL 2.221,86",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
            obrigatorio=True,
        )
        CampoExtraido.objects.create(
            regiao=self.comprovante,
            esquema="comprovante_transferencia",
            chave="beneficiario",
            rotulo="Beneficiário",
            valor_original="LUCIANE SAURIN",
            valor_normalizado="LUCIANE SAURIN",
            numero_pagina=17,
            trecho_evidencia="CLIENTE: LUCIANE SAURIN",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
            obrigatorio=True,
        )
        CampoExtraido.objects.create(
            regiao=self.holerite,
            esquema="holerite",
            chave="valor_liquido",
            rotulo="Valor líquido",
            valor_original="2.221,86",
            valor_normalizado="2221.86",
            numero_pagina=17,
            trecho_evidencia="Total Líquido 2.221,86",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
            obrigatorio=True,
        )
        CampoExtraido.objects.create(
            regiao=self.holerite,
            esquema="holerite",
            chave="total_proventos",
            rotulo="Total de proventos",
            valor_original="2.433,24",
            valor_normalizado="2433.24",
            numero_pagina=17,
            trecho_evidencia="Total 2.433,24 211,38",
            metodo="ocr_regiao",
            obrigatorio=True,
        )
        CampoExtraido.objects.create(
            regiao=self.holerite,
            esquema="holerite",
            chave="total_descontos",
            rotulo="Total de descontos",
            valor_original="211,38",
            valor_normalizado="211.38",
            numero_pagina=17,
            trecho_evidencia="Total 2.433,24 211,38",
            metodo="ocr_regiao",
            obrigatorio=True,
        )
        CampoExtraido.objects.create(
            regiao=self.holerite,
            esquema="holerite",
            chave="funcionario",
            rotulo="Funcionário",
            valor_original="LUCIANE SAURIN BIZOTO",
            valor_normalizado="LUCIANE SAURIN BIZOTO",
            numero_pagina=17,
            trecho_evidencia="17 LUCIANE SAURIN BIZOTO",
            metodo="ocr_regiao",
            estado_revisao=EstadoCampo.PENDENTE,
            obrigatorio=True,
        )

    def test_interface_recolhida_evidencia_e_contexto(self):
        resposta = self.client.get(reverse("laboratorio:curadoria", kwargs={"lote_pk": self.lote.pk}) + "?pagina=17")
        self.assertContains(resposta, "Separação automática preliminar — revisão pendente")
        self.assertNotContains(resposta, "segmentacao_heuristica_multipessa")
        self.assertNotContains(resposta, "faixa_em_branco")
        self.assertNotContains(resposta, "Y relativo")
        self.assertContains(resposta, "<details class=\"secao-peca\">")
        self.assertNotContains(resposta, "secao-peca\" open")
        self.assertContains(resposta, "Evidência — página 17:")
        self.assertContains(resposta, "Expandir tudo")
        self.assertContains(resposta, "Recolher tudo")
        self.assertContains(resposta, "Etapa de Execução")
        self.assertContains(resposta, "Classificação e Extração")
        self.assertContains(resposta, "SCC 3350/2022")
        self.assertContains(resposta, "2022TR000929")
        self.assertContains(resposta, "vínculo cadastral pendente")
        self.assertContains(resposta, "SCC 00004208/2023")
        self.assertContains(resposta, "não comprova o pagamento")
        self.assertNotContains(resposta, "pagamento comprovado")
        self.assertNotContains(resposta, "despesa elegível")
        css = (Path(settings.BASE_DIR) / "aplicacao" / "static" / "css" / "cge.css").read_text(encoding="utf-8")
        self.assertIn(".evidencia-campo", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.hash_sha256, self.hash_original)
        self.assertEqual(self.lote.documento.nome_original, "Processo SCC 00004208_2023 - parcial 01.pdf")

    def test_comparacao_demonstrativa(self):
        comparacao = comparar_pagina([self.holerite, self.comprovante])
        self.assertTrue(comparacao["valores_iguais"])
        self.assertTrue(comparacao["aritmetica_ok"])
        self.assertIn("Correspondência sugerida", comparacao["nomes"])
        self.assertEqual(comparacao["estado_humano"], "pendente")

    def test_revisao_persiste_sem_confirmar_sozinha(self):
        campo = self.holerite.campos.get(chave="funcionario")
        url = reverse("laboratorio:revisar_campo", kwargs={"lote_pk": self.lote.pk, "campo_pk": campo.pk})
        self.client.post(url, {"acao": "corrigir", "valor_original": "Outro Nome", "justificativa": ""})
        campo.refresh_from_db()
        self.assertEqual(campo.valor_original, "LUCIANE SAURIN BIZOTO")
        self.assertEqual(campo.estado_revisao, EstadoCampo.PENDENTE)
        self.client.post(url, {"acao": "confirmar", "valor_original": campo.valor_original, "justificativa": ""})
        campo.refresh_from_db()
        self.assertEqual(campo.estado_revisao, EstadoCampo.CONFIRMADO)
        self.assertEqual(len(campo.historico_correcoes), 1)
        self.client.post(
            url,
            {"acao": "corrigir", "valor_original": "Luciane Saurin Bizoto", "justificativa": "Grafia conferida no original."},
        )
        campo.refresh_from_db()
        self.assertEqual(campo.estado_revisao, EstadoCampo.CORRIGIDO)
        self.assertEqual(campo.valor_original, "Luciane Saurin Bizoto")
        self.assertEqual(len(campo.historico_correcoes), 2)
        self.assertEqual(campo.historico_correcoes[-1]["usuario"], "auditor-ciclo602")

    def test_ajuste_visual_nao_confirma_classificacao(self):
        url = reverse(
            "laboratorio:ajustar_regiao",
            kwargs={"lote_pk": self.lote.pk, "regiao_pk": self.holerite.pk},
        )
        resposta = self.client.post(url, {"x": "0.05", "y": "0.42", "largura": "0.9", "altura": "0.5"})
        self.assertEqual(resposta.status_code, 200)
        self.holerite.refresh_from_db()
        self.assertEqual(self.holerite.metodo_deteccao, "ajuste_humano")
        self.assertEqual(self.holerite.estado_classificacao, EstadoClassificacao.PROPOSTO)
        self.assertEqual(self.holerite.estado_revisao, EstadoRevisao.PENDENTE)
        self.assertAlmostEqual(self.holerite.y, 0.42)

    def test_instrumento_do_lote_permanece_pendente(self):
        identificacao = montar_identificacao(self.prestacao)
        self.assertEqual(identificacao["instrumento_documental"]["numero"], "2022TR000929")
        self.assertTrue(identificacao["instrumento_documental"]["pendente"])
        detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(detalhe, "2022TR000929")
        self.assertContains(detalhe, "Vínculo cadastral pendente")
