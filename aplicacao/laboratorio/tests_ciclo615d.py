"""Ciclo 6.1.5-D: amostra de encargos sem duplicar obrigação nem confirmar pagamento."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfWriter

from aplicacao.laboratorio.conciliacao import _cadeias_darf, _cadeias_fgts
from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoVinculo
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.incorporacao import (
    PAGINAS_615D,
    VERSAO_615D,
    ErroIncorporacao,
    _completar_comprovantes,
    _gravar_cadeias_novas,
    _unir_fragmentos,
    incorporar_amostra,
)
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()

DARF_JUNHO = """
Receita Federal Documento de Arrecadação de Receitas Federais
CNPJ 92.419.958/0001-47
Período de Apuração 06/2022
Data de Vencimento 20/07/2022
Número do Documento 07.16.22178.0408098-2
Código da Receita 1082
Valor Total do Documento
2.494,74
"""

RODAPE_JUNHO = """
AUTENTICAÇÃO MECÂNICA
Documento de Arrecadação de Receitas Federais
07.16.22178.0408098-2
"""

RECIBO_SEM_VALOR = """
COMPROVANTE DE PAGAMENTO DE DARF/DARF SIMPLES
DATA DO PAGAMENTO 82/06/2022
PERIODO DE APURACAO 31/12/2022
VALOR TOTAL
"""


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class Ciclo615dTests(TestCase):
    def test_le_o_darf_de_junho_e_rejeita_data_impossivel(self):
        campos = {item["chave"]: item for item in extrair_campos("darf", DARF_JUNHO, 124, "teste")}
        self.assertEqual(campos["total"]["valor_normalizado"], "2494.74")
        self.assertEqual(campos["codigo_receita"]["valor_original"], "1082")
        self.assertEqual(campos["periodo_apuracao"]["valor_original"], "06/2022")
        self.assertEqual(campos["numero_documento"]["valor_original"], "07.16.22178.0408098-2")
        self.assertEqual(campos["vencimento"]["valor_original"], "20/07/2022")
        self.assertEqual(campos["total"]["numero_pagina"], 124)
        recibo = {item["chave"]: item for item in extrair_campos("comprovante_darf", RECIBO_SEM_VALOR, 126, "teste")}
        self.assertEqual(recibo["valor"]["valor_original"], "")
        self.assertEqual(recibo["data_pagamento"]["valor_original"], "")
        self.assertEqual(recibo["data_pagamento"]["estado_confianca"], "inconsistente")

    def test_vincula_pelo_numero_e_separa_fgts_de_competencia_diferente(self):
        with TemporaryDirectory(prefix="ciclo615d-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                junho = self._peca(
                    lote,
                    124,
                    "darf",
                    [
                        ("total", "2.494,74", "2494.74"),
                        ("numero_documento", "07.16.22178.0408098-2", "07.16.22178.0408098-2"),
                        ("codigo_receita", "1082", "1082"),
                        ("periodo_apuracao", "06/2022", "06/2022"),
                    ],
                )
                recibo = self._peca(
                    lote,
                    125,
                    "comprovante_darf",
                    [
                        ("valor", "2.494,74", "2494.74"),
                        ("numero_documento", "07.16.22178.0408098-2", "07.16.22178.0408098-2"),
                    ],
                )
                mesmo_valor = self._peca(
                    lote,
                    126,
                    "comprovante_darf",
                    [("valor", "2.494,74", "2494.74"), ("numero_documento", "07.16.22999.0000001-9", "07.16.22999.0000001-9")],
                )
                guia = self._peca(
                    lote,
                    123,
                    "guia_fgts",
                    [("valor_recolhimento", "2.200,02", "2200.02"), ("competencia", "07/2022", "07/2022")],
                )
                self._peca(lote, 123, "comprovante_fgts", [])
                vizinho = self._peca(
                    lote,
                    127,
                    "comprovante_fgts",
                    [("valor", "2.200,02", "2200.02"), ("competencia", "87/2022", "87/2022")],
                )
                propostas = {item["execucao"].pk: item for item in _cadeias_darf(lote, list(lote.regioes.all()))}
                self.assertEqual(propostas[junho.pk]["comprovante"].pk, recibo.pk)
                self.assertNotEqual(propostas[junho.pk]["comprovante"].pk, mesmo_valor.pk)
                fgts = {item["execucao"].pk: item for item in _cadeias_fgts(lote, list(lote.regioes.all()))}
                self.assertIsNone(fgts[guia.pk]["comprovante"])
                self.assertNotEqual(fgts[guia.pk].get("comprovante"), vizinho)

    def test_idempotencia_preserva_decisao_e_nao_cria_cadeia_fora_da_amostra(self):
        with TemporaryDirectory(prefix="ciclo615d-id-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                junho = self._peca(
                    lote,
                    124,
                    "darf",
                    [("total", "2.494,74", "2494.74"), ("numero_documento", "07.16.22178.0408098-2", "07.16.22178.0408098-2")],
                )
                campo = junho.campos.get(chave="total")
                campo.estado_revisao = EstadoCampo.CONFIRMADO
                campo.save(update_fields=["estado_revisao"])
                primeira = incorporar_amostra(lote, [124], versao=VERSAO_615D)
                segunda = incorporar_amostra(lote, [124], versao=VERSAO_615D)
                self.assertEqual(primeira[0]["situacao"], "ja_incorporada")
                self.assertEqual(segunda[0]["situacao"], "ja_incorporada")
                self.assertEqual(lote.paginas.get(numero_fisico=124).regioes.count(), 1)
                campo.refresh_from_db()
                self.assertEqual(campo.estado_revisao, EstadoCampo.CONFIRMADO)
                antiga = self._peca(
                    lote,
                    122,
                    "guia_fgts",
                    [("valor_recolhimento", "2.218,35", "2218.35")],
                    versao="6.1.5-c",
                )
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [122], versao=VERSAO_615D)
                self.assertEqual(antiga.versao_extracao, "6.1.5-c")
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [126], versao=VERSAO_615D)
                with self.assertRaises(ErroIncorporacao):
                    incorporar_amostra(lote, [17], versao=VERSAO_615D)
                fraca = self._peca(lote, 126, "darf", [("total", "671,33", "671.33")])
                self.assertNotIn(126, PAGINAS_615D)
                criadas = _gravar_cadeias_novas(lote)
                self.assertEqual(criadas, [f"fgts-{antiga.pk}"])
                self.assertEqual(_gravar_cadeias_novas(lote), [])
                self.assertFalse(lote.cadeias.filter(execucao=fraca).exists())

    def test_fragmentos_nao_duplicam_o_total_e_o_painel_nao_confirma_pagamento(self):
        with TemporaryDirectory(prefix="ciclo615d-painel-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                pagina = self._pagina(lote, 124)
                formulario = self._regiao(lote, pagina, "darf", DARF_JUNHO)
                self._regiao(lote, pagina, "darf", RODAPE_JUNHO)
                _unir_fragmentos(pagina)
                self.assertEqual(pagina.regioes.filter(tipo_documental="darf").count(), 1)
                formulario.refresh_from_db()
                total = formulario.campos.get(chave="total")
                self.assertEqual(total.valor_normalizado, "2494.74")
                self.assertEqual(total.numero_pagina, 124)
                self.assertEqual(formulario.pagina.numero_fisico, 124)
                recibo = self._peca(
                    lote,
                    125,
                    "comprovante_darf",
                    [
                        ("valor", "2.494,74", "2494.74"),
                        ("numero_documento", "07.16.22178.0408098-2", "07.16.22178.0408098-2"),
                    ],
                )
                guia = self._peca(lote, 123, "guia_fgts", [("valor_recolhimento", "2.200,02", "2200.02")])
                self._peca(lote, 123, "comprovante_fgts", [])
                incerto = self._peca(
                    lote,
                    131,
                    "darf",
                    [("total", "2.574,61", "2574.61"), ("principal", "2.574,60", "2574.60")],
                )
                incerto.campos.filter(chave="total").update(estado_confianca="inconsistente")
                guia_antiga = self._peca(lote, 112, "darf", [("total", "2.428,92", "2428.92")])
                preservada = CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo=f"darf-{guia_antiga.pk}",
                    titulo="Cadeia já homologada",
                    execucao=guia_antiga,
                    comprovante=self._peca(lote, 113, "comprovante_darf", [("valor", "2.428,92", "2428.92")]),
                    estado=EstadoVinculo.SUGERIDO,
                    verificacoes=[{"codigo": "preservada"}],
                    revisado_por=None,
                )
                criadas = _gravar_cadeias_novas(lote)
                self.assertEqual(_gravar_cadeias_novas(lote), [])
                self.assertIn(f"darf-{formulario.pk}", criadas)
                self.assertIn(f"fgts-{guia.pk}", criadas)
                self.assertIn(f"darf-{incerto.pk}", criadas)
                complementos = _completar_comprovantes(lote)
                self.assertEqual(_completar_comprovantes(lote), [])
                self.assertEqual(complementos, [])
                cadeia = lote.cadeias.get(codigo=f"darf-{formulario.pk}")
                self.assertEqual(cadeia.estado, EstadoVinculo.SUGERIDO)
                self.assertEqual(cadeia.comprovante_id, recibo.pk)
                self.assertIsNone(cadeia.revisado_por_id)
                preservada.refresh_from_db()
                self.assertEqual(preservada.verificacoes, [{"codigo": "preservada"}])
                self.assertEqual(preservada.comprovante.pagina.numero_fisico, 113)
                fgts = lote.cadeias.get(codigo=f"fgts-{guia.pk}")
                self.assertIsNone(fgts.comprovante_id)
                painel = montar_conferencia_integrada(lote)
                self.assertEqual(painel["executado_decimal"], Decimal("2494.74") + Decimal("2200.02") + Decimal("2428.92"))
                self.assertEqual(painel["sugerido_decimal"], Decimal("2494.74") + Decimal("2428.92"))
                self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
                self.assertEqual(lote.cadeias.filter(codigo=f"darf-{formulario.pk}").count(), 1)

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        usuario = Usuario.objects.create_user(
            username=f"auditor-615d-{PrestacaoContas.objects.count()}",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-615D", criado_por=usuario)
        return importar_pdf(
            prestacao=prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-ciclo615d",
            usuario=usuario,
        )

    def _pagina(self, lote, numero):
        return InventarioPagina.objects.create(lote=lote, numero_fisico=numero, quantidade_regioes=1)

    def _regiao(self, lote, pagina, tipo, texto, versao=VERSAO_615D):
        return RegiaoDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            tipo_documental=tipo,
            ordem=pagina.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=texto,
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
            trecho_evidencia=original,
            metodo="teste",
            estado_confianca="evidencia_textual" if original else "ausente",
            estado_revisao=EstadoCampo.PENDENTE if original else EstadoCampo.AUSENTE,
        )

    def _peca(self, lote, numero, tipo, campos, versao=VERSAO_615D):
        pagina = lote.paginas.filter(numero_fisico=numero).first() or self._pagina(lote, numero)
        regiao = self._regiao(lote, pagina, tipo, tipo, versao=versao)
        for chave, original, normalizado in campos:
            self._campo(regiao, chave, original, normalizado)
        return regiao
