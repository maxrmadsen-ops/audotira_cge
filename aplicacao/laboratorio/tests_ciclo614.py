"""Ciclo 6.1.4: conferência integrada sem contar duas vezes e sem gravar ao consultar."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.laboratorio.conferencia_integrada import montar_conferencia_integrada
from aplicacao.laboratorio.escolhas import EstadoVinculo
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import importar_pdf
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, PlanoTrabalho, PrestacaoContas

Usuario = get_user_model()


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


class TesteConferenciaIntegrada(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="auditor-ciclo614",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        self.prestacao = PrestacaoContas.objects.create(numero_processo="SCC-CICLO-614", criado_por=self.usuario)
        self.client.force_login(self.usuario)
        with TemporaryDirectory(prefix="ciclo614-") as temporario:
            raiz = Path(temporario) / "docs"
            raiz.mkdir(parents=True, exist_ok=True)
            with override_settings(DOCUMENTOS_RAIZ=str(raiz)):
                caminho = raiz / "parcial.pdf"
                caminho.write_bytes(_pdf())
                self.lote = importar_pdf(
                    prestacao=self.prestacao,
                    caminho=caminho,
                    numero_processo_parcial="SCC 00004208/2023",
                    numero_instrumento="2022TR000929",
                    origem="teste-ciclo614",
                    usuario=self.usuario,
                )
        self.plano = PlanoTrabalho.objects.create(
            prestacao=self.prestacao,
            titulo="Plano de demonstração",
            valor_global=Decimal("673370.28"),
            status_revisao=StatusRevisaoPlano.AGUARDANDO,
        )
        self.item_pessoal = self._item(1, "Pagamento de despesas com profissionais", Decimal("296664.71"), StatusRevisaoPlano.CONFIRMADO)
        self.item_fgts = self._item(9, "Despesas com FGTS", Decimal("17700.00"), StatusRevisaoPlano.AGUARDANDO)
        self.item_rescisao = self._item(11, "Despesas com rescisões", Decimal("71193.93"), StatusRevisaoPlano.AGUARDANDO)
        self.item_vazio = self._item(2, "Contratação de professores", Decimal("88096.11"), StatusRevisaoPlano.CONFIRMADO)
        self.holerite = self._regiao(17, "holerite", "valor_liquido", "2221.86", "2.221,86")
        self.transferencia_folha = self._regiao(17, "comprovante_transferencia", "valor", "2221.86", "2.221,86")
        self.rescisao = self._regiao(91, "termo_rescisao", "total_liquido", "4166.51", "4.166,51")
        self.quitacao = self._regiao(92, "termo_quitacao", "valor_quitado", "", "")
        self.transferencia_rescisao = self._regiao(93, "comprovante_transferencia", "valor", "4166.51", "4.166,51")
        self.guia_a = self._regiao(111, "guia_fgts", "valor_recolhimento", "2329.85", "2.329,85")
        self.guia_b = self._regiao(116, "guia_fgts", "valor_recolhimento", "2242.43", "2.242,43")
        self.cadeia_folha = self._cadeia("folha-882", self.item_pessoal, self.holerite, self.transferencia_folha, None)
        self.cadeia_rescisao = self._cadeia("rescisao-911", self.item_rescisao, self.rescisao, self.transferencia_rescisao, self.quitacao)
        self.cadeia_guia_a = self._cadeia("fgts-893", self.item_fgts, self.guia_a, None, None)
        self.cadeia_guia_b = self._cadeia("fgts-891", self.item_fgts, self.guia_b, None, None)

    def _item(self, ordem, descricao, valor, status):
        return ItemPlanoTrabalho.objects.create(
            plano=self.plano,
            ordem=ordem,
            descricao=descricao,
            valor_previsto=valor,
            status_revisao=status,
        )

    def _regiao(self, pagina, tipo, chave, normalizado, original):
        inventario, _criada = InventarioPagina.objects.get_or_create(
            lote=self.lote,
            numero_fisico=pagina,
            defaults={"quantidade_regioes": 1},
        )
        regiao = RegiaoDocumental.objects.create(
            lote=self.lote,
            pagina=inventario,
            tipo_documental=tipo,
            ordem=inventario.regioes.count() + 1,
            metodo_deteccao="teste",
            texto_regiao=tipo,
        )
        CampoExtraido.objects.create(
            regiao=regiao,
            esquema=tipo,
            chave=chave,
            rotulo=chave,
            valor_original=original,
            valor_normalizado=normalizado,
            numero_pagina=pagina,
            metodo="ocr_regiao",
            estado_confianca="evidencia_textual" if normalizado else "ausente",
        )
        return regiao

    def _cadeia(self, codigo, item, execucao, comprovante, apoio):
        return CadeiaConciliacao.objects.create(
            lote=self.lote,
            codigo=codigo,
            titulo=codigo,
            item_plano=item,
            criterio_item="Sugestão pela descrição. O orçamento anual não é esta parcela.",
            execucao=execucao,
            comprovante=comprovante,
            apoio=apoio,
            verificacoes=[{"codigo": "amostra", "situacao": "pendente", "titulo": "Amostra"}],
            estado=EstadoVinculo.SUGERIDO,
        )

    def _linha(self, painel, item_id):
        return next(linha for linha in painel["linhas"] if linha["item_id"] == item_id)

    def test_agrega_os_tres_itens_sem_somar_apoio_nem_comprovante(self):
        painel = montar_conferencia_integrada(self.lote)
        pessoal = self._linha(painel, self.item_pessoal.id)
        rescisao = self._linha(painel, self.item_rescisao.id)
        fgts = self._linha(painel, self.item_fgts.id)
        self.assertEqual(pessoal["executado_decimal"], Decimal("2221.86"))
        self.assertEqual(pessoal["sugerido_decimal"], Decimal("2221.86"))
        self.assertEqual(rescisao["executado_decimal"], Decimal("4166.51"))
        self.assertEqual(rescisao["sugerido_decimal"], Decimal("4166.51"))
        self.assertEqual(fgts["executado_decimal"], Decimal("4572.28"))
        self.assertEqual(fgts["sugerido_decimal"], Decimal("0.00"))
        self.assertEqual(painel["executado_decimal"], Decimal("10960.65"))
        self.assertEqual(painel["sugerido_decimal"], Decimal("6388.37"))
        self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
        self.assertEqual(fgts["situacao_codigo"], "sem_comprovante")
        self.assertEqual(pessoal["situacao_codigo"], "sugerida")
        self.assertIn(self.holerite.pk, [peca["peca_id"] for peca in pessoal["pecas"]])
        self.assertIn(self.transferencia_folha.pk, [peca["peca_id"] for peca in pessoal["pecas"]])
        self.assertIn(self.quitacao.pk, [peca["peca_id"] for peca in rescisao["pecas"]])

    def test_item_sem_documento_nao_vira_irregularidade_nem_saldo(self):
        linha = self._linha(montar_conferencia_integrada(self.lote), self.item_vazio.id)
        self.assertEqual(linha["situacao_codigo"], "sem_execucao")
        self.assertEqual(linha["previsto_decimal"], Decimal("88096.11"))
        self.assertEqual(linha["executado_decimal"], Decimal("0.00"))
        self.assertIn("não indica irregularidade", linha["explicacao"])
        self.assertNotIn("saldo", linha["explicacao"])

    def test_peca_repetida_entra_uma_vez_e_sugestao_nao_vira_confirmacao(self):
        self._cadeia("folha-duplicada", self.item_pessoal, self.holerite, self.transferencia_folha, None)
        painel = montar_conferencia_integrada(self.lote)
        pessoal = self._linha(painel, self.item_pessoal.id)
        self.assertEqual(pessoal["executado_decimal"], Decimal("2221.86"))
        self.assertEqual(pessoal["sugerido_decimal"], Decimal("2221.86"))
        self.assertEqual(painel["confirmado_decimal"], Decimal("0.00"))
        self.assertTrue(any("não foi contada de novo" in peca["nota"].lower() for peca in pessoal["pecas"]))

    def test_confirmacao_humana_separa_o_comprovante_da_sugestao(self):
        self.cadeia_folha.estado = EstadoVinculo.CONFIRMADO
        self.cadeia_folha.save(update_fields=["estado"])
        painel = montar_conferencia_integrada(self.lote)
        pessoal = self._linha(painel, self.item_pessoal.id)
        self.assertEqual(pessoal["confirmado_decimal"], Decimal("2221.86"))
        self.assertEqual(pessoal["sugerido_decimal"], Decimal("0.00"))
        self.assertEqual(painel["sugerido_decimal"], Decimal("4166.51"))
        self.assertEqual(painel["confirmado_decimal"], Decimal("2221.86"))
        self.assertEqual(pessoal["situacao_codigo"], "confirmada")

    def test_valor_ambiguo_nao_entra_na_soma(self):
        campo = self.guia_a.campos.get(chave="valor_recolhimento")
        campo.estado_confianca = "ambiguo"
        campo.save(update_fields=["estado_confianca"])
        fgts = self._linha(montar_conferencia_integrada(self.lote), self.item_fgts.id)
        self.assertEqual(fgts["executado_decimal"], Decimal("2242.43"))
        self.assertEqual(fgts["situacao_codigo"], "insuficiente")

    def test_divergencia_entre_documentos_nao_e_irregularidade(self):
        campo = self.transferencia_rescisao.campos.get(chave="valor")
        campo.valor_normalizado = "4000.00"
        campo.valor_original = "4.000,00"
        campo.save(update_fields=["valor_normalizado", "valor_original"])
        linha = self._linha(montar_conferencia_integrada(self.lote), self.item_rescisao.id)
        self.assertEqual(linha["situacao_codigo"], "divergencia")
        self.assertEqual(linha["executado_decimal"], Decimal("4166.51"))
        self.assertEqual(linha["sugerido_decimal"], Decimal("4000.00"))
        self.assertIn("não foi classificada como irregularidade", linha["explicacao"])

    def test_consulta_nao_grava_cadeias_nem_a_conciliacao_recria_vinculo(self):
        antes = list(
            CadeiaConciliacao.objects.filter(lote=self.lote).order_by("codigo").values(
                "codigo", "estado", "execucao_id", "comprovante_id", "apoio_id", "verificacoes"
            )
        )
        extra = self._regiao(18, "holerite", "valor_liquido", "100.00", "100,00")
        resposta = self.client.get(reverse("laboratorio:conferencia_integrada", kwargs={"lote_pk": self.lote.pk}))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Conferência integrada")
        self.assertContains(resposta, "10.960,65")
        self.assertContains(resposta, "Não indica ausência de pagamento real")
        self.assertContains(resposta, "folha-882")
        self.assertContains(resposta, f"peca={self.holerite.pk}")
        self.assertNotContains(resposta, "pagamento comprovado")
        self.assertNotContains(resposta, "despesa aprovada")
        consulta = self.client.get(reverse("laboratorio:conciliacao", kwargs={"lote_pk": self.lote.pk}))
        self.assertEqual(consulta.status_code, 200)
        self.assertContains(consulta, "Global do plano")
        self.assertContains(consulta, "Execução identificada")
        self.assertContains(consulta, "Correspondência sugerida")
        self.assertContains(consulta, "Pagamento confirmado")
        self.assertContains(consulta, "Confirmar vínculo")
        self.assertContains(consulta, "não confirma pagamento")
        self.assertNotContains(consulta, "pagamento comprovado")
        self.assertNotContains(consulta, "despesa elegível")
        depois = list(
            CadeiaConciliacao.objects.filter(lote=self.lote).order_by("codigo").values(
                "codigo", "estado", "execucao_id", "comprovante_id", "apoio_id", "verificacoes"
            )
        )
        self.assertEqual(antes, depois)
        self.assertFalse(CadeiaConciliacao.objects.filter(lote=self.lote, execucao=extra).exists())
        self.cadeia_rescisao.refresh_from_db()
        self.assertEqual(self.cadeia_rescisao.codigo, "rescisao-911")
        self.assertEqual(self.cadeia_rescisao.estado, EstadoVinculo.SUGERIDO)
        self.assertEqual(self.holerite.versao_extracao, "")
        self.assertEqual(
            {self.holerite.pagina.numero_fisico, self.rescisao.pagina.numero_fisico, self.quitacao.pagina.numero_fisico, self.transferencia_rescisao.pagina.numero_fisico},
            {17, 91, 92, 93},
        )
