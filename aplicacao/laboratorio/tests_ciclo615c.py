"""Ciclo 6.1.5-C: amostra que completa cadeias sem somar comprovante nem confirmar pagamento."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.laboratorio.classificacao import classificar_texto, dividir_comprovante_e_guia, tipo_principal
from aplicacao.laboratorio.conciliacao import _cadeias_darf, _cadeias_fgts
from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoVinculo
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.incorporacao import (
    ErroIncorporacao,
    _completar_comprovantes,
    _gravar_cadeias_novas,
    incorporar_amostra,
)
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()

DARF_PIS = """
Documento de Arrecadação de Receitas Federais
PERÍODO DE APURAÇÃO
30/04/2022
CÓDIGO DA RECEITA 8301
02.419.958/0001-47
07 VALOR DO PRINCIPAL
275,93
08 VALORDA MULTA 0,00
09 VALOR DOS JUROS E/OU
ENCARGOS DL-1025/69
É vedado o recolhimento cujo valor total seja inferior a R$ 10,00.
LOR TOTAL
10 VA 275,98
"""

DARF_IRRF = """
Documento de Arrecadação de Receitas Federais
DARF - IRRF
É vedado o recolhimento cujo valor total seja inferior a R$ 10,00.
02 PERÍODO DE APURAÇÃO S1/052022
CÓDIGO DA RECEITA
0561
07 VALOR DO PRINCIPAL
671,33
08 VALOR DA MULTA
0,00
09 VALOR DOS JUROS E/OU
ENCARGOS DL-1025/69
10 VALOR TOTAL
671,33
"""

DARF_PREV = """
Documento de Arrecadação de Receitas Federais
Periodo de Apuração Data de Vencimento
01/03/2022 20/04/2022
Número: 07.16.22137.6425585-7
Valor Total do Documento
2.708,32
Totais 2.471,56 212,05 24,71 2.708,32
PA 03/2022 Vencimento 20/04/2022
Valor: 2.708,32
"""

RECIBO_FGTS = """
COMPROVANTE DE PAGAMENTO
Convenio FGTS ARRECADACAO GRF
COMPETENCIA 10/2022
VALOR DEPOSITO 2.218,35
Valor Total 2.218,35
"""

GUIA_FGTS = """
GRF - GUIA DE RECOLHIMENTO DO FGTS
FUNDO DE GARANTIA DO TEMPO DE SERVICO
GFIP-SEFIP
11-COMPETÊNCIA
10/2022
15-TOTAL A RECOLHER
2.218,35
"""


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class Ciclo615cTests(TestCase):
    def test_separa_recibo_de_guia_e_nao_trata_o_aviso_de_dez_reais_como_total(self):
        self.assertEqual(tipo_principal(classificar_texto(RECIBO_FGTS), RECIBO_FGTS)["tipo"], "comprovante_fgts")
        self.assertEqual(tipo_principal(classificar_texto(GUIA_FGTS), GUIA_FGTS)["tipo"], "guia_fgts")
        palavras_darf = [{"texto": "MINISTERIO", "y": 0.58}, {"texto": "arrecadador", "y": 0.2}]
        self.assertEqual(
            dividir_comprovante_e_guia(
                "COMPROVANTE DE PAGAMENTO DE DARF\nDocumento de Arrecadação de Receitas Federais",
                palavras_darf,
            ),
            0.56,
        )
        palavras_fgts = [{"texto": "GRF", "y": 0.22}, {"texto": "FUNDO", "y": 0.61}, {"texto": "GFIP", "y": 0.64}]
        self.assertEqual(dividir_comprovante_e_guia(RECIBO_FGTS + "\n" + GUIA_FGTS, palavras_fgts), 0.59)
        self.assertIsNone(
            dividir_comprovante_e_guia(
                "Documento de Arrecadação de Receitas Federais\nValor Total do Documento\n2.708,32",
                [{"texto": "FEDERAIS", "y": 0.4}],
            )
        )
        pis = {item["chave"]: item for item in extrair_campos("darf", DARF_PIS, 109, "teste")}
        self.assertEqual(pis["principal"]["valor_normalizado"], "275.93")
        self.assertEqual(pis["total"]["valor_original"], "275,98")
        self.assertEqual(pis["total"]["estado_confianca"], "inconsistente")
        irrf = {item["chave"]: item for item in extrair_campos("darf", DARF_IRRF, 119, "teste")}
        self.assertEqual(irrf["total"]["valor_normalizado"], "671.33")
        self.assertEqual(irrf["codigo_receita"]["valor_original"], "0561")
        self.assertNotEqual(irrf["total"]["estado_confianca"], "inconsistente")
        prev = {item["chave"]: item for item in extrair_campos("darf", DARF_PREV, 114, "teste")}
        self.assertEqual(prev["total"]["valor_normalizado"], "2708.32")
        self.assertEqual(prev["numero_documento"]["valor_original"], "07.16.22137.6425585-7")
        sem_valor = {item["chave"]: item for item in extrair_campos("comprovante_darf", """
COMPROVANTE DE PAGAMENTO DE DARF/DARF SIMPLES
PERIODO DE APURACAO 31/05/2022
CODIGO DE RECEITA 0561
VALOR DO PRINCIPAL
VALOR TOTAL
""", 120, "teste")}
        self.assertEqual(sem_valor["valor"]["valor_original"], "")
        self.assertEqual(sem_valor["periodo_apuracao"]["valor_original"], "31/05/2022")

    def test_vincula_pelo_numero_e_nao_pelo_valor_sozinho(self):
        with TemporaryDirectory(prefix="ciclo615c-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                guia = self._obrigacao(
                    lote,
                    112,
                    "darf",
                    [("total", "2.428,92", "2428.92"), ("numero_documento", "07.16.22116.4889373-0", "07.16.22116.4889373-0")],
                )
                recibo = self._obrigacao(
                    lote,
                    113,
                    "comprovante_darf",
                    [("valor", "2.428,92", "2428.92"), ("numero_documento", "07.16.22116.4889373-0", "07.16.22116.4889373-0")],
                )
                maio = self._obrigacao(
                    lote,
                    119,
                    "darf",
                    [
                        ("total", "671,33", "671.33"),
                        ("codigo_receita", "0561", "0561"),
                        ("periodo_apuracao", "31/05/2022", "31/05/2022"),
                    ],
                )
                junho = self._obrigacao(
                    lote,
                    121,
                    "darf",
                    [
                        ("total", "671,33", "671.33"),
                        ("codigo_receita", "0561", "0561"),
                        ("periodo_apuracao", "30/06/2022", "30/06/2022"),
                    ],
                )
                self._obrigacao(
                    lote,
                    121,
                    "comprovante_darf",
                    [
                        ("valor", "671,33", "671.33"),
                        ("codigo_receita", "0561", "0561"),
                        ("periodo_apuracao", "30/06/2022", "30/06/2022"),
                    ],
                )
                parecido = self._obrigacao(
                    lote,
                    114,
                    "darf",
                    [("total", "100,00", "100.00"), ("numero_documento", "07.16.22137.6425585-7", "07.16.22137.6425585-7")],
                )
                self._obrigacao(
                    lote,
                    115,
                    "comprovante_darf",
                    [("valor", "100,00", "100.00"), ("numero_documento", "97.16.22137.6425585-7", "97.16.22137.6425585-7")],
                )
                propostas = {item["execucao"].pk: item for item in _cadeias_darf(lote, list(lote.regioes.all()))}
                self.assertEqual(propostas[guia.pk]["comprovante"].pk, recibo.pk)
                self.assertIsNone(propostas[maio.pk]["comprovante"])
                self.assertEqual(propostas[junho.pk]["comprovante"].pagina.numero_fisico, 121)
                self.assertIsNone(propostas[parecido.pk]["comprovante"])

    def test_completa_cadeia_sugerida_sem_regravar_decisao_nem_somar_duas_vezes(self):
        with TemporaryDirectory(prefix="ciclo615c-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                self.client.force_login(lote.prestacao_parceria.criado_por)
                folha_pagina = self._pagina(lote, 17)
                holerite = self._regiao(lote, folha_pagina, "holerite")
                self._campo(holerite, "valor_liquido", "2.221,86", "2221.86")
                transferencia = self._regiao(lote, folha_pagina, "comprovante_transferencia")
                self._campo(transferencia, "valor", "2.221,86", "2221.86")
                folha = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo=f"folha-{holerite.pk}",
                    titulo="Folha preservada",
                    execucao=holerite,
                    comprovante=transferencia,
                    estado=EstadoVinculo.SUGERIDO,
                    verificacoes=[{"codigo": "preservada"}],
                )
                fgts_antigo = self._obrigacao(lote, 116, "guia_fgts", [("valor_recolhimento", "2.242,43", "2242.43"), ("competencia", "05/2022", "05/2022")])
                fgts_cadeia = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo=f"fgts-{fgts_antigo.pk}",
                    titulo="FGTS preservado",
                    execucao=fgts_antigo,
                    estado=EstadoVinculo.SUGERIDO,
                    verificacoes=[{"codigo": "preservada"}],
                )
                guia = self._obrigacao(
                    lote,
                    112,
                    "darf",
                    [("total", "2.428,92", "2428.92"), ("numero_documento", "07.16.22116.4889373-0", "07.16.22116.4889373-0")],
                    versao="6.1.5-b",
                )
                darf = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo=f"darf-{guia.pk}",
                    titulo="DARF preservado",
                    execucao=guia,
                    estado=EstadoVinculo.SUGERIDO,
                    verificacoes=[{"codigo": "preservada"}],
                )
                self._obrigacao(
                    lote,
                    113,
                    "comprovante_darf",
                    [("valor", "2.428,92", "2428.92"), ("numero_documento", "07.16.22116.4889373-0", "07.16.22116.4889373-0")],
                    versao="6.1.5-c",
                )
                novo = self._obrigacao(
                    lote,
                    114,
                    "darf",
                    [("total", "2.708,32", "2708.32"), ("numero_documento", "07.16.22137.6425585-7", "07.16.22137.6425585-7")],
                    versao="6.1.5-c",
                )
                self._obrigacao(
                    lote,
                    115,
                    "comprovante_darf",
                    [("valor", "2.788,32", "2788.32"), ("numero_documento", "97.16.22137.6425585-7", "97.16.22137.6425585-7")],
                    versao="6.1.5-b",
                )
                maio = self._obrigacao(lote, 119, "darf", [("total", "671,33", "671.33"), ("codigo_receita", "0561", "0561"), ("periodo_apuracao", "05/2022", "05/2022")], versao="6.1.5-c")
                self._obrigacao(lote, 120, "comprovante_darf", [("codigo_receita", "0561", "0561"), ("periodo_apuracao", "31/05/2022", "31/05/2022")], versao="6.1.5-c")
                junho = self._obrigacao(lote, 121, "darf", [("total", "671,33", "671.33"), ("codigo_receita", "0561", "0561"), ("periodo_apuracao", "06/2022", "06/2022")], versao="6.1.5-c")
                incerto = self._obrigacao(lote, 109, "darf", [("total", "275,98", "275.98"), ("principal", "275,93", "275.93"), ("codigo_receita", "8301", "8301")], versao="6.1.5-c")
                incerto.campos.filter(chave="total").update(estado_confianca="inconsistente")
                self._obrigacao(lote, 110, "comprovante_darf", [("valor", "275,93", "275.93"), ("codigo_receita", "8301", "8301"), ("periodo_apuracao", "30/04/2022", "30/04/2022")], versao="6.1.5-b")
                guia_nova = self._obrigacao(lote, 122, "guia_fgts", [("valor_recolhimento", "2.218,35", "2218.35"), ("competencia", "10/2022", "10/2022")], versao="6.1.5-c")
                self._obrigacao(lote, 122, "comprovante_fgts", [("valor", "2.218,35", "2218.35"), ("competencia", "10/2022", "10/2022")], versao="6.1.5-c")
                decidida = self._obrigacao(
                    lote,
                    16,
                    "darf",
                    [
                        ("total", "10,00", "10.00"),
                        ("numero_documento", "07.16.22999.0000001-1", "07.16.22999.0000001-1"),
                    ],
                    versao="6.1.5-b",
                )
                cadeia_decidida = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo=f"darf-{decidida.pk}",
                    titulo="Decisão humana",
                    execucao=decidida,
                    estado=EstadoVinculo.CONFIRMADO,
                    verificacoes=[{"codigo": "humana"}],
                )
                self._obrigacao(
                    lote,
                    18,
                    "comprovante_darf",
                    [("valor", "10,00", "10.00"), ("numero_documento", "07.16.22999.0000001-1", "07.16.22999.0000001-1")],
                    versao="6.1.5-b",
                )
                criadas = _gravar_cadeias_novas(lote)
                complementos = _completar_comprovantes(lote)
                self.assertEqual(_gravar_cadeias_novas(lote), [])
                self.assertEqual(_completar_comprovantes(lote), [])
                self.assertIn(f"darf-{novo.pk}", criadas)
                self.assertIn(f"darf-{maio.pk}", criadas)
                self.assertIn(f"darf-{junho.pk}", criadas)
                self.assertIn(f"fgts-{guia_nova.pk}", criadas)
                self.assertNotIn(f"darf-{guia.pk}", criadas)
                self.assertNotIn(f"fgts-{fgts_antigo.pk}", criadas)
                darf.refresh_from_db()
                folha.refresh_from_db()
                fgts_cadeia.refresh_from_db()
                cadeia_decidida.refresh_from_db()
                self.assertEqual(complementos, [darf.codigo])
                self.assertEqual(darf.estado, EstadoVinculo.SUGERIDO)
                self.assertEqual(darf.comprovante.pagina.numero_fisico, 113)
                self.assertEqual(folha.verificacoes, [{"codigo": "preservada"}])
                self.assertEqual(fgts_cadeia.verificacoes, [{"codigo": "preservada"}])
                self.assertIsNone(cadeia_decidida.comprovante_id)
                self.assertEqual(cadeia_decidida.verificacoes, [{"codigo": "humana"}])
                propostas_fgts = {item["execucao"].pk: item for item in _cadeias_fgts(lote, list(lote.regioes.all()))}
                self.assertEqual(propostas_fgts[guia_nova.pk]["comprovante"].pagina.numero_fisico, 122)
                self.assertIsNone(propostas_fgts[fgts_antigo.pk]["comprovante"])
                painel = montar_conferencia_integrada(lote)
                self.assertEqual(
                    painel["executado_decimal"],
                    Decimal("2221.86") + Decimal("2242.43") + Decimal("2428.92") + Decimal("2708.32") + Decimal("671.33") + Decimal("671.33") + Decimal("2218.35") + Decimal("10.00"),
                )
                self.assertEqual(painel["sugerido_decimal"], Decimal("2221.86") + Decimal("2428.92") + Decimal("2218.35"))
                self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
                self.assertEqual(lote.cadeias.filter(codigo=f"darf-{incerto.pk}").count(), 1)
                resposta = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}) + "?pagina=114")
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "114")
                self.assertContains(resposta, str(novo.pk))
                curadoria = self.client.get(
                    reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}) + f"?pagina=114&peca={novo.pk}"
                )
                self.assertEqual(curadoria.status_code, 200)
                self.assertContains(curadoria, "2.708,32")
                conciliacao = self.client.get(reverse("laboratorio:conciliacao", kwargs={"lote_pk": lote.pk}))
                self.assertEqual(conciliacao.status_code, 200)
                self.assertContains(conciliacao, "Execução identificada")
                self.assertContains(conciliacao, "Pagamento confirmado")
                self.assertContains(conciliacao, "não comprova pagamento")
                self.assertContains(conciliacao, "não confirma pagamento")
                self.assertNotContains(conciliacao, "pagamento comprovado")
                self.assertNotContains(conciliacao, "despesa elegível")
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [17])
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [8])
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [109, 200])

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        usuario = Usuario.objects.create_user(
            username=f"auditor-615c-{PrestacaoContas.objects.count()}",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-615C", criado_por=usuario)
        return importar_pdf(
            prestacao=prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-ciclo615c",
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

    def _campo(self, regiao, chave, original, normalizado, confianca=""):
        return CampoExtraido.objects.create(
            regiao=regiao,
            esquema=regiao.tipo_documental,
            chave=chave,
            rotulo=chave,
            valor_original=original,
            valor_normalizado=normalizado,
            numero_pagina=regiao.pagina.numero_fisico,
            metodo="teste",
            estado_confianca=confianca or ("evidencia_textual" if original else "ausente"),
            estado_revisao=EstadoCampo.PENDENTE if original else EstadoCampo.AUSENTE,
        )

    def _obrigacao(self, lote, numero, tipo, campos, versao="6.1.5-c"):
        pagina = lote.paginas.filter(numero_fisico=numero).first() or self._pagina(lote, numero)
        regiao = self._regiao(lote, pagina, tipo, versao=versao)
        for chave, original, normalizado in campos:
            self._campo(regiao, chave, original, normalizado)
        return regiao
