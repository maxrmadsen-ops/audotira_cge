"""Ciclo 6.1.5-A: cobertura, menções administrativas e descoberta sem alterar totais."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao
from aplicacao.documentos.models import PaginaDocumento
from aplicacao.laboratorio.classificacao import candidatos_da_peca, classificar_texto
from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada, montar_cobertura
from aplicacao.laboratorio.descoberta import ErroDescoberta, corrigir_mencoes, inspecionar_paginas
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoRevisao, EstadoVinculo
from aplicacao.laboratorio.models import (
    CadeiaConciliacao,
    CampoExtraido,
    InventarioPagina,
    RegiaoDocumental,
    RevisaoLaboratorio,
    VinculoEvidencia,
)
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, PlanoTrabalho, PrestacaoContas

Usuario = get_user_model()

EMAIL = """
06/03/2023 E-mail de Secretaria de Estado da Casa Civil de SC
https://mail.google.com/mail/u/0/
9 anexos
BALANCETE DE PRESTAÇÃO DE CONTAS.PDF
folha de pagamento 10-22.PDF
folhas de pagamento 04-22.PDF
OFÍCIO JUSTIFICATIVA.PDF
"""

DESENTRANHAMENTO = """
Sistema de Gestão de Processos Eletrônicos - SGP-e
TERMO DE DESENTRANHAMENTO
As páginas 8 até 8 desta peça foram desentranhadas.
Motivo: Incluído Arquivo Atualizado correspondente ao Balancete.
Documento assinado digitalmente.
"""

BALANCETE = """
Balancete de verificação da parceria
Período 01/04/2022 a 30/04/2022
Receitas do período 10.000,00
Despesas do período 8.000,00
"""


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


class TesteCoberturaEDescoberta(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo615a",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-615A", criado_por=self.usuario)
        self.client.force_login(self.usuario)

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        return importar_pdf(
            prestacao=self.prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-ciclo615a",
            usuario=self.usuario,
        )

    def _pagina(self, lote, numero, texto, tecnica="nativo", caracteres=None):
        documento = PaginaDocumento.objects.create(
            documento=lote.documento,
            numero_pagina=numero,
            texto_extraido=texto,
            metodo_extracao=MetodoExtracao.NATIVO if tecnica == "nativo" else MetodoExtracao.OCR,
            qualidade_extracao=QualidadeExtracao.SUFICIENTE if len(texto) > 40 else QualidadeExtracao.INSUFICIENTE,
            quantidade_caracteres=len(texto),
        )
        return InventarioPagina.objects.create(
            lote=lote,
            pagina_documento=documento,
            numero_fisico=numero,
            tecnica_utilizada=tecnica,
            quantidade_caracteres=len(texto) if caracteres is None else caracteres,
            quantidade_regioes=0,
        )

    def _regiao(self, lote, pagina, tipo, chave="titulo", original="", confianca="evidencia_textual"):
        regiao = RegiaoDocumental.objects.create(
            lote=lote,
            pagina=pagina,
            tipo_documental=tipo,
            ordem=pagina.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=original or tipo,
            estado_revisao=EstadoRevisao.PENDENTE,
        )
        CampoExtraido.objects.create(
            regiao=regiao,
            esquema=tipo,
            chave=chave,
            rotulo=chave,
            valor_original=original,
            valor_normalizado=original.replace(".", "").replace(",", ".") if original else "",
            numero_pagina=pagina.numero_fisico,
            metodo="teste",
            estado_confianca=confianca if original else "ausente",
            estado_revisao=EstadoCampo.PENDENTE if original else EstadoCampo.AUSENTE,
        )
        return regiao

    def test_indicadores_sao_calculados(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                pagina = self._pagina(lote, 1, "texto administrativo suficiente para a página", caracteres=80)
                outra = self._pagina(lote, 2, "outra página com texto longo o bastante", caracteres=80)
                curta = self._pagina(lote, 3, "12", caracteres=2)
                self._pagina(lote, 4, "9", tecnica="ocr", caracteres=1)
                financeira = self._regiao(lote, pagina, "holerite", "valor_liquido", "2.221,86")
                self._regiao(lote, pagina, "oficio_encaminhamento", "titulo", "Ofício interno")
                self._regiao(lote, outra, "administrativo_sgpe", "titulo", "")
                planilha = ItemPlanoTrabalho.objects.create(
                    plano=PlanoTrabalho.objects.create(
                        prestacao=self.prestacao,
                        titulo="Plano",
                        valor_global=Decimal("673370.28"),
                        status_revisao=StatusRevisaoPlano.AGUARDANDO,
                    ),
                    ordem=1,
                    descricao="Profissionais",
                    valor_previsto=Decimal("296664.71"),
                    status_revisao=StatusRevisaoPlano.CONFIRMADO,
                )
                CadeiaConciliacao.objects.create(
                    lote=lote,
                    codigo="folha-882",
                    titulo="folha-882",
                    item_plano=planilha,
                    execucao=financeira,
                    estado=EstadoVinculo.SUGERIDO,
                )
                destino = RegiaoDocumental.objects.get(lote=lote, tipo_documental="oficio_encaminhamento")
                terceira = RegiaoDocumental.objects.get(lote=lote, tipo_documental="administrativo_sgpe")
                terceira.estado_revisao = EstadoRevisao.REVISADA
                terceira.save(update_fields=["estado_revisao"])
                VinculoEvidencia.objects.create(
                    lote=lote, origem=financeira, destino=destino, tipo_vinculo="amostra", estado=EstadoVinculo.SUGERIDO
                )
                VinculoEvidencia.objects.create(
                    lote=lote, origem=destino, destino=terceira, tipo_vinculo="amostra", estado=EstadoVinculo.CONFIRMADO
                )
                cobertura = montar_cobertura(lote)
                self.assertEqual(cobertura["pecas"], 3)
                self.assertEqual(cobertura["paginas_com_peca"], 2)
                self.assertEqual(cobertura["com_campo"], 2)
                self.assertEqual(cobertura["com_valor"], 1)
                self.assertEqual(cobertura["vinculadas"], 1)
                self.assertEqual(cobertura["vinculos_sugeridos"], 1)
                self.assertEqual(cobertura["vinculos_confirmados"], 1)
                self.assertEqual(cobertura["pendentes"], 2)
                self.assertEqual(cobertura["sem_ocr"], 1)
                self.assertNotEqual(curta.quantidade_caracteres, 231)

    def test_mencao_de_anexo_nao_classifica_balancete_nem_folha(self):
        tipos_email = {item["tipo"] for item in candidatos_da_peca(classificar_texto(EMAIL), EMAIL)}
        self.assertNotIn("balancete", tipos_email)
        self.assertNotIn("folha_pagamento", tipos_email)
        self.assertNotIn("oficio_encaminhamento", tipos_email)
        tipos_balancete = {item["tipo"] for item in candidatos_da_peca(classificar_texto(BALANCETE), BALANCETE)}
        self.assertIn("balancete", tipos_balancete)
        folha = "Folha de pagamento\nCompetência: 03/2022\nTotal líquido: R$ 2.221,86\n"
        tipos_folha = {item["tipo"] for item in candidatos_da_peca(classificar_texto(folha), folha)}
        self.assertIn("folha_pagamento", tipos_folha)
        oficio = "Ofício de encaminhamento da prestação de contas parcial."
        tipos_oficio = {item["tipo"] for item in candidatos_da_peca(classificar_texto(oficio), oficio)}
        self.assertIn("oficio_encaminhamento", tipos_oficio)

    def test_termo_administrativo_permanece_e_mencao_e_reclassificada(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                pagina = self._pagina(lote, 9, DESENTRANHAMENTO)
                sgpe = self._regiao(lote, pagina, "administrativo_sgpe", "titulo", "TERMO DE DESENTRANHAMENTO")
                balancete = self._regiao(lote, pagina, "balancete", "periodo", "")
                campo_id = balancete.campos.get().pk
                email = self._pagina(lote, 238, EMAIL)
                folha = self._regiao(lote, email, "folha_pagamento", "competencia", "")
                resultado = corrigir_mencoes(lote, self.usuario)
                balancete.refresh_from_db()
                sgpe.refresh_from_db()
                folha.refresh_from_db()
                self.assertEqual(balancete.tipo_documental, "administrativo_sgpe")
                self.assertEqual(sgpe.tipo_documental, "administrativo_sgpe")
                self.assertEqual(folha.tipo_documental, "outros_nao_classificados")
                self.assertTrue(CampoExtraido.objects.filter(pk=campo_id, regiao=balancete).exists())
                self.assertIn("balancete", balancete.justificativa)
                revisao = RevisaoLaboratorio.objects.get(lote=lote, alvo="regiao", alvo_id=balancete.pk)
                self.assertEqual(revisao.detalhe["tipo_anterior"], "balancete")
                self.assertEqual(revisao.acao, "reclassificar_mencao")
                self.assertTrue(any(item["situacao"] == "reclassificada" for item in resultado))

    def test_consulta_nao_grava(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                pagina = self._pagina(lote, 17, "holerite de demonstração", caracteres=80)
                self._regiao(lote, pagina, "holerite", "valor_liquido", "2.221,86")
                antes = list(CadeiaConciliacao.objects.filter(lote=lote).values_list("codigo", "estado"))
                revisoes = RevisaoLaboratorio.objects.filter(lote=lote).count()
                resposta = self.client.get(reverse("laboratorio:conferencia_integrada", kwargs={"lote_pk": lote.pk}))
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "Peças classificadas")
                self.assertContains(resposta, "Não é percentual de execução financeira do plano.")
                self.assertEqual(list(CadeiaConciliacao.objects.filter(lote=lote).values_list("codigo", "estado")), antes)
                self.assertEqual(RevisaoLaboratorio.objects.filter(lote=lote).count(), revisoes)

    def test_ocr_so_nas_paginas_pedidas(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                self._pagina(lote, 8, "8", caracteres=1)

                class Extrator:
                    def __init__(self):
                        self.chamadas = []

                    def extrair_pagina(self, caminho, numero):
                        self.chamadas.append(numero)
                        return BALANCETE, []

                extrator = Extrator()
                inspecionar_paginas(lote, [8], extrator)
                inspecionar_paginas(lote, [8], extrator)
                self.assertEqual(extrator.chamadas, [8])
                with self.assertRaises(ErroDescoberta):
                    inspecionar_paginas(lote, [17], extrator)
                with self.assertRaises(ErroDescoberta):
                    inspecionar_paginas(lote, list(range(1, 20)), extrator)
                self.assertEqual(extrator.chamadas, [8])

    def test_cadeias_homologadas_permanecem(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                plano = PlanoTrabalho.objects.create(
                    prestacao=self.prestacao,
                    titulo="Plano",
                    valor_global=Decimal("673370.28"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                pessoal = ItemPlanoTrabalho.objects.create(
                    plano=plano, ordem=1, descricao="Profissionais", valor_previsto=Decimal("296664.71"),
                    status_revisao=StatusRevisaoPlano.CONFIRMADO,
                )
                rescisao_item = ItemPlanoTrabalho.objects.create(
                    plano=plano, ordem=11, descricao="Rescisões", valor_previsto=Decimal("71193.93"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                pagina_folha = self._pagina(lote, 17, "holerite", caracteres=80)
                pagina_rescisao = self._pagina(lote, 91, "rescisão", caracteres=80)
                holerite = self._regiao(lote, pagina_folha, "holerite", "valor_liquido", "2.221,86")
                rescisao = self._regiao(lote, pagina_rescisao, "termo_rescisao", "total_liquido", "4.166,51")
                CadeiaConciliacao.objects.create(
                    lote=lote, codigo="folha-882", titulo="folha-882", item_plano=pessoal,
                    execucao=holerite, estado=EstadoVinculo.SUGERIDO,
                )
                CadeiaConciliacao.objects.create(
                    lote=lote, codigo="rescisao-911", titulo="rescisao-911", item_plano=rescisao_item,
                    execucao=rescisao, estado=EstadoVinculo.SUGERIDO,
                )
                corrigir_mencoes(lote, self.usuario)
                for codigo, tipo in (("folha-882", "holerite"), ("rescisao-911", "termo_rescisao")):
                    cadeia = CadeiaConciliacao.objects.get(lote=lote, codigo=codigo)
                    self.assertEqual(cadeia.estado, EstadoVinculo.SUGERIDO)
                    self.assertEqual(cadeia.execucao.tipo_documental, tipo)

    def test_fgts_nao_duplica_o_valor(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                plano = PlanoTrabalho.objects.create(
                    prestacao=self.prestacao,
                    titulo="Plano",
                    valor_global=Decimal("673370.28"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                item = ItemPlanoTrabalho.objects.create(
                    plano=plano, ordem=9, descricao="FGTS", valor_previsto=Decimal("17700.00"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                for numero, codigo, valor, original in (
                    (111, "fgts-893", "2329.85", "2.329,85"),
                    (116, "fgts-891", "2242.43", "2.242,43"),
                ):
                    pagina = self._pagina(lote, numero, "guia", caracteres=80)
                    regiao = self._regiao(lote, pagina, "guia_fgts", "valor_recolhimento", original)
                    regiao.texto_regiao = (
                        "COMPROVANTE DE PAGAMENTO\nConvenio FGTS ARRECADACAO GRF\n"
                        f"VALOR DEPOSITO {original}\nAUTENTICACAO SISBB: 9.F11.CBC.91A.D82.065"
                    )
                    regiao.save(update_fields=["texto_regiao"])
                    CampoExtraido.objects.create(
                        regiao=regiao,
                        esquema="fgts",
                        chave="autenticacao",
                        rotulo="Autenticação",
                        valor_original="9.F11.CBC.91A.D82.065",
                        valor_normalizado="9.F11.CBC.91A.D82.065",
                        numero_pagina=numero,
                        metodo="teste",
                        estado_confianca="ambiguo",
                        estado_revisao=EstadoCampo.PENDENTE,
                    )
                    CadeiaConciliacao.objects.create(
                        lote=lote, codigo=codigo, titulo=codigo, item_plano=item,
                        execucao=regiao, estado=EstadoVinculo.SUGERIDO,
                    )
                painel = montar_conferencia_integrada(lote)
                self.assertEqual(painel["executado_decimal"], Decimal("4572.28"))
                self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
                self.assertEqual(painel["sugerido_decimal"], Decimal("0.00"))
                linha = next(item_linha for item_linha in painel["linhas"] if item_linha["ordem"] == 9)
                self.assertEqual(len(linha["pecas"]), 2)
                self.assertEqual(CadeiaConciliacao.objects.filter(lote=lote).count(), 2)
                for peca in linha["pecas"]:
                    self.assertIn("Guia e obrigação identificadas", peca["nota"])
                    self.assertIn("Comprovante bancário localizado na mesma peça", peca["nota"])
                    self.assertIn("Autenticação ambígua", peca["nota"])
                    self.assertIn("Recolhimento pendente de confirmação do auditor", peca["nota"])
                    self.assertNotIn("pagamento comprovado", peca["nota"].lower())

    def test_totais_homologados_permanecem_apos_descoberta(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                plano = PlanoTrabalho.objects.create(
                    prestacao=self.prestacao,
                    titulo="Plano",
                    valor_global=Decimal("673370.28"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                pessoal = ItemPlanoTrabalho.objects.create(
                    plano=plano, ordem=1, descricao="Profissionais", valor_previsto=Decimal("296664.71"),
                    status_revisao=StatusRevisaoPlano.CONFIRMADO,
                )
                fgts = ItemPlanoTrabalho.objects.create(
                    plano=plano, ordem=9, descricao="FGTS", valor_previsto=Decimal("17700.00"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                rescisao_item = ItemPlanoTrabalho.objects.create(
                    plano=plano, ordem=11, descricao="Rescisões", valor_previsto=Decimal("71193.93"),
                    status_revisao=StatusRevisaoPlano.AGUARDANDO,
                )
                pares = (
                    (17, "holerite", "valor_liquido", "2.221,86", pessoal, "folha-882"),
                    (111, "guia_fgts", "valor_recolhimento", "2.329,85", fgts, "fgts-893"),
                    (116, "guia_fgts", "valor_recolhimento", "2.242,43", fgts, "fgts-891"),
                    (91, "termo_rescisao", "total_liquido", "4.166,51", rescisao_item, "rescisao-911"),
                )
                for numero, tipo, chave, original, item, codigo in pares:
                    pagina = self._pagina(lote, numero, tipo, caracteres=80)
                    regiao = self._regiao(lote, pagina, tipo, chave, original)
                    CadeiaConciliacao.objects.create(
                        lote=lote, codigo=codigo, titulo=codigo, item_plano=item,
                        execucao=regiao, estado=EstadoVinculo.SUGERIDO,
                    )
                self._pagina(lote, 8, "8", caracteres=1)

                class Extrator:
                    def extrair_pagina(self, caminho, numero):
                        return BALANCETE, []

                antes = montar_conferencia_integrada(lote)
                inspecionar_paginas(lote, [8], Extrator())
                depois = montar_conferencia_integrada(lote)
                self.assertEqual(antes["valor_global_decimal"], Decimal("673370.28"))
                self.assertEqual(depois["valor_global_decimal"], Decimal("673370.28"))
                self.assertEqual(depois["executado_decimal"], Decimal("10960.65"))
                self.assertEqual(depois["sugerido_decimal"], Decimal("0.00"))
                self.assertEqual(depois["confirmado_decimal"], Decimal("0.00"))
                self.assertEqual(depois["executado_decimal"], antes["executado_decimal"])
                self.assertFalse(CadeiaConciliacao.objects.filter(lote=lote, estado=EstadoVinculo.CONFIRMADO).exists())

    def test_descoberta_registra_evidencia_sem_confirmar_pagamento(self):
        with TemporaryDirectory(prefix="ciclo615a-") as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                self._pagina(lote, 8, "8", caracteres=1)
                regioes_antes = lote.regioes.count()

                class Extrator:
                    def extrair_pagina(self, caminho, numero):
                        return BALANCETE, []

                registros = inspecionar_paginas(lote, [8], Extrator())
                detalhe = registros[0]
                self.assertEqual(detalhe["numero"], 8)
                self.assertEqual(detalhe["texto_nativo"], "8")
                self.assertIn("Balancete", detalhe["texto_ocr"])
                self.assertEqual(detalhe["tipo"], "balancete")
                self.assertTrue(detalhe["revisao_humana"])
                self.assertFalse(detalhe["altera_totais"])
                self.assertTrue(detalhe["campos_financeiros"])
                self.assertEqual(lote.regioes.count(), regioes_antes)
                self.assertFalse(CadeiaConciliacao.objects.filter(lote=lote).exists())
                self.assertFalse(VinculoEvidencia.objects.filter(lote=lote, estado=EstadoVinculo.CONFIRMADO).exists())
                revisao = RevisaoLaboratorio.objects.get(lote=lote, alvo="descoberta_pagina", alvo_id=8)
                self.assertEqual(revisao.detalhe["numero"], 8)
