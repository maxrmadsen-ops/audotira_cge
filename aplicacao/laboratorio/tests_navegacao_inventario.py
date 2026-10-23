"""Navegação do inventário: contagem, busca por peça e inspeção complementar."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao
from aplicacao.documentos.models import PaginaDocumento
from aplicacao.laboratorio.conferencia_integrada import montar_cobertura
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoClassificacao, EstadoRevisao
from aplicacao.laboratorio.models import CampoExtraido, InventarioPagina, RegiaoDocumental, RevisaoLaboratorio
from aplicacao.laboratorio.servico import importar_pdf, montar_relatorio
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class NavegacaoInventarioTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-navegacao",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="SCC-NAVEGACAO", criado_por=self.usuario)
        self.client.force_login(self.usuario)

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        return importar_pdf(
            prestacao=self.prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-navegacao",
            usuario=self.usuario,
        )

    def _pagina(self, lote, numero, impresso="", tipos=None, estado=EstadoClassificacao.INCONCLUSIVO):
        documento = PaginaDocumento.objects.create(
            documento=lote.documento,
            numero_pagina=numero,
            texto_extraido=str(numero),
            metodo_extracao=MetodoExtracao.NATIVO,
            qualidade_extracao=QualidadeExtracao.INSUFICIENTE,
            quantidade_caracteres=2,
        )
        return InventarioPagina.objects.create(
            lote=lote,
            pagina_documento=documento,
            numero_fisico=numero,
            numero_impresso=impresso,
            tipos_candidatos=tipos or [],
            estado_classificacao=estado,
            tecnica_utilizada="nativo",
            quantidade_caracteres=2,
            quantidade_regioes=0,
        )

    def _regiao(self, lote, pagina, tipo):
        return RegiaoDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            tipo_documental=tipo,
            ordem=pagina.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=tipo,
            estado_revisao=EstadoRevisao.PENDENTE,
        )

    def test_registros_separam_pecas_efetivas_e_placeholders(self):
        with TemporaryDirectory(prefix="navegacao-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                pagina = self._pagina(lote, 17, impresso="15", tipos=["comprovante_transferencia"], estado=EstadoClassificacao.PROPOSTO)
                self._regiao(lote, pagina, "comprovante_transferencia")
                self._regiao(lote, pagina, "holerite")
                self._regiao(lote, pagina, "guia_fgts")
                self._regiao(lote, pagina, "outros_nao_classificados")
                relatorio = montar_relatorio(lote)
                cobertura = montar_cobertura(lote)
                self.assertEqual(relatorio["pecas_registros"], 4)
                self.assertEqual(relatorio["pecas_efetivas"], 3)
                self.assertEqual(relatorio["pecas_identificadas"], 3)
                self.assertEqual(relatorio["pecas_placeholder"], 1)
                self.assertEqual(relatorio["pecas_total"], 4)
                self.assertEqual(cobertura["pecas"], 4)
                self.assertEqual(cobertura["pecas_efetivas"], 3)
                self.assertEqual(cobertura["pecas_placeholder"], 1)
                inventario = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}))
                self.assertContains(inventario, "Registros de peças")
                self.assertContains(inventario, "peças efetivas")
                self.assertContains(inventario, "menções sem documento")
                self.assertContains(inventario, "páginas com candidatos documentais")

    def test_busca_por_identificador_abre_a_peca_mesmo_com_varias_na_pagina(self):
        with TemporaryDirectory(prefix="navegacao-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                pagina = self._pagina(lote, 17, impresso="15", tipos=["holerite"])
                self._pagina(lote, 18)
                primeira = self._regiao(lote, pagina, "comprovante_transferencia")
                segunda = self._regiao(lote, pagina, "holerite")
                placeholder = self._regiao(lote, pagina, "outros_nao_classificados")
                antes = list(lote.regioes.values_list("pk", "tipo_documental", "estado_classificacao"))
                inventario = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}), {"peca": segunda.pk})
                self.assertEqual(inventario.status_code, 200)
                self.assertContains(inventario, f"peca={segunda.pk}")
                self.assertContains(inventario, "Página física")
                self.assertContains(inventario, "Página impressa")
                self.assertContains(inventario, ">17<")
                self.assertContains(inventario, ">15<")
                self.assertNotContains(inventario, ">18<")
                por_pagina = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}), {"pagina": 17})
                self.assertContains(por_pagina, str(primeira.pk))
                self.assertContains(por_pagina, str(segunda.pk))
                conferencia = self.client.get(
                    reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}),
                    {"pagina": 17, "peca": segunda.pk},
                )
                self.assertContains(conferencia, "peca-ativa")
                self.assertContains(conferencia, f"Peça {segunda.pk}")
                self.assertContains(conferencia, "página física do PDF 17")
                self.assertContains(conferencia, "página impressa 15")
                placeholder_tela = self.client.get(
                    reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk}),
                    {"pagina": 17, "peca": placeholder.pk},
                )
                self.assertContains(placeholder_tela, f"Peça {placeholder.pk}")
                self.assertContains(placeholder_tela, "peca-ativa")
                self.assertEqual(list(lote.regioes.values_list("pk", "tipo_documental", "estado_classificacao")), antes)

    def test_inspecao_complementar_permanece_fora_da_classificacao(self):
        with TemporaryDirectory(prefix="navegacao-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                inspecionada = self._pagina(lote, 16)
                self._pagina(lote, 17, impresso="15", tipos=["holerite"], estado=EstadoClassificacao.PROPOSTO)
                RevisaoLaboratorio.objects.create(
                    lote=lote,
                    alvo="descoberta_pagina",
                    alvo_id=16,
                    acao="inspecao_ocr",
                    justificativa="Amostra complementar.",
                    detalhe={"numero": 16, "altera_totais": False},
                )
                resposta = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}))
                self.assertContains(resposta, "Inspeção complementar disponível. A classificação do inventário permanece.")
                self.assertContains(resposta, "Inconclusiva")
                filtrada = self.client.get(reverse("laboratorio:lote", kwargs={"lote_pk": lote.pk}), {"inspecao": "sim"})
                self.assertContains(filtrada, ">16<")
                self.assertNotContains(filtrada, ">17<")
                inspecionada.refresh_from_db()
                self.assertEqual(inspecionada.estado_classificacao, EstadoClassificacao.INCONCLUSIVO)
                self.assertEqual(CampoExtraido.objects.filter(regiao__lote=lote).count(), 0)
