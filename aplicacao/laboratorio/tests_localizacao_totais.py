"""Localização dos totais do TRCT: caixa exata quando o token é único, faixa quando não é."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from aplicacao.laboratorio.escolhas import EstadoCampo
from aplicacao.laboratorio.localizacao import caixa_de_digitos, faixa_total_aproximada, projetar_faixa_vertical
from aplicacao.laboratorio.models import CampoExtraido, InventarioPagina, RegiaoDocumental
from aplicacao.laboratorio.servico import _com_proveniencia, _localizacao_do_total, aplicar_localizacao_campo, importar_pdf
from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


def _pdf() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    destino = BytesIO()
    escritor.write(destino)
    return destino.getvalue()


class LocalizacaoTotaisTests(TestCase):
    def test_token_unico_vira_caixa_e_repeticao_nao_vira(self):
        palavras = [
            {"texto": "7.811,51", "x": 0.89, "y": 0.2, "largura": 0.05, "altura": 0.3},
            {"texto": "outro", "x": 0.1, "y": 0.2, "largura": 0.1, "altura": 0.3},
        ]
        caixa = caixa_de_digitos(palavras, "781151")
        self.assertEqual(caixa["x"], 0.89)
        self.assertIsNone(caixa_de_digitos(palavras + [dict(palavras[0])], "781151"))
        larga = [{"texto": "7.811,51", "x": 0.1, "y": 0.2, "largura": 0.5, "altura": 0.3}]
        self.assertIsNone(caixa_de_digitos(larga, "781151"))
        juntos = [
            {"texto": "7.811", "x": 0.88, "y": 0.2, "largura": 0.04, "altura": 0.3},
            {"texto": ",51", "x": 0.93, "y": 0.21, "largura": 0.02, "altura": 0.3},
        ]
        unida = caixa_de_digitos(juntos, "781151")
        self.assertAlmostEqual(unida["largura"], 0.07, places=2)

    def test_faixa_sem_token_permanece_aproximada_e_a_projecao_nao_inventa_largura(self):
        faixa = faixa_total_aproximada(0.896, 0.932)
        self.assertFalse(faixa["localizacao_precisa"])
        self.assertEqual(faixa["evidencia_largura"], 1.0)
        self.assertEqual(faixa["evidencia_y"], 0.896)
        dados = {
            "text": ["7.811,51"],
            "left": [890],
            "top": [20],
            "width": [50],
            "height": [30],
        }
        local = _localizacao_do_total(dados, (1000, 100), "7.811,51", 0.896, 0.932)
        self.assertTrue(local["localizacao_precisa"])
        self.assertEqual(local["evidencia_x"], 0.89)
        self.assertLess(local["evidencia_largura"], 0.4)
        self.assertGreater(local["evidencia_y"], 0.896)
        self.assertLess(local["evidencia_y"], 0.932)
        vazia = _localizacao_do_total({"text": [], "left": [], "top": [], "width": [], "height": []}, (1000, 100), "7.811,51", 0.896, 0.932)
        self.assertFalse(vazia["localizacao_precisa"])
        self.assertEqual(vazia["evidencia_largura"], 1.0)
        projetada = projetar_faixa_vertical({"x": 0.5, "y": 0.0, "largura": 0.1, "altura": 1.0}, 0.7, 0.74)
        self.assertEqual(projetada["evidencia_y"], 0.7)

    def test_gravar_caixa_nao_muda_valor_e_a_segunda_vez_nao_duplica_a_frase(self):
        with TemporaryDirectory() as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                campo = self._campo(lote, "total_liquido", "7.811,51", "7811.51")
                antes = (campo.valor_original, campo.valor_normalizado, campo.estado_revisao, campo.estado_confianca, campo.metodo)
                aplicar_localizacao_campo(
                    campo,
                    {
                        "evidencia_x": 0.899,
                        "evidencia_y": 0.901,
                        "evidencia_largura": 0.049,
                        "evidencia_altura": 0.009,
                        "localizacao_precisa": True,
                    },
                )
                campo.refresh_from_db()
                self.assertEqual(
                    (campo.valor_original, campo.valor_normalizado, campo.estado_revisao, campo.estado_confianca, campo.metodo),
                    antes,
                )
                self.assertTrue(campo.localizacao_precisa)
                self.assertEqual(campo.evidencia_x, 0.899)
                self.assertEqual(campo.trecho_evidencia.count("Localização exata"), 1)
                aplicar_localizacao_campo(
                    campo,
                    {
                        "evidencia_x": 0.899,
                        "evidencia_y": 0.901,
                        "evidencia_largura": 0.049,
                        "evidencia_altura": 0.009,
                        "localizacao_precisa": True,
                    },
                )
                campo.refresh_from_db()
                self.assertEqual(campo.trecho_evidencia.count("Localização exata"), 1)
                self.assertEqual(campo.valor_original, "7.811,51")
                self.assertEqual(_com_proveniencia(campo.trecho_evidencia, False).count("Localização"), 1)
                self.assertIn("aproximada", _com_proveniencia(campo.trecho_evidencia, False))

    def test_curadoria_mostra_o_pdf_e_distingue_destaque_aproximado(self):
        with TemporaryDirectory() as temporario:
            with override_settings(DOCUMENTOS_RAIZ=temporario):
                lote = self._lote(temporario)
                bruto = self._campo(lote, "total_bruto", "8.942,66", "8942.66")
                deducoes = self._campo(lote, "deducoes", "1.131,15", "1131.15")
                liquido = self._campo(lote, "total_liquido", "7.811,51", "7811.51")
                bruto.localizacao_precisa = True
                bruto.evidencia_x, bruto.evidencia_y = 0.902, 0.721
                bruto.evidencia_largura, bruto.evidencia_altura = 0.05, 0.009
                bruto.save()
                deducoes.localizacao_precisa = False
                deducoes.evidencia_x, deducoes.evidencia_y = 0.0, 0.866
                deducoes.evidencia_largura, deducoes.evidencia_altura = 1.0, 0.064
                deducoes.save()
                usuario = Usuario.objects.get(username__startswith="auditor-local-")
                self.client.force_login(usuario)
                resposta = self.client.get(
                    reverse("laboratorio:curadoria", kwargs={"lote_pk": lote.pk})
                    + f"?pagina=88&peca={bruto.regiao_id}&destaque=total_liquido"
                )
                self.assertEqual(resposta.status_code, 200)
                html = resposta.content.decode()
                self.assertEqual(html.count("Mostrar no PDF"), 2)
                self.assertEqual(html.count("Destaque aproximado da faixa lida, não do valor isolado."), 1)
                self.assertIn("Página de origem", html)
                self.assertIn("abrir-pagina-origem", html)
                self.assertIn('classList.toggle("aproximado"', html)
                self.assertIn("botaoPedido.click()", html)
                self.assertIn('data-chave="total_bruto"', html)
                self.assertIn('data-aproximada="1"', html)
                self.assertIn('data-x="0.902000"', html)
                self.assertNotIn('data-x="0,902', html)
                bruto.refresh_from_db()
                deducoes.refresh_from_db()
                liquido.refresh_from_db()
                self.assertEqual(bruto.valor_original, "8.942,66")
                self.assertEqual(deducoes.valor_original, "1.131,15")
                self.assertEqual(liquido.valor_original, "7.811,51")
                self.assertFalse(liquido.localizacao_precisa)

    def _lote(self, raiz):
        caminho = Path(raiz) / "parcial.pdf"
        caminho.write_bytes(_pdf())
        usuario = Usuario.objects.create_user(
            username=f"auditor-local-{PrestacaoContas.objects.count()}",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="SCC-LOCAL-TOTAIS", criado_por=usuario)
        return importar_pdf(
            prestacao=prestacao,
            caminho=caminho,
            numero_processo_parcial="SCC 00004208/2023",
            numero_instrumento="2022TR000929",
            origem="teste-localizacao",
            usuario=usuario,
        )

    def _campo(self, lote, chave, original, normalizado):
        pagina = lote.paginas.filter(numero_fisico=88).first()
        if pagina is None:
            pagina = InventarioPagina.objects.create(lote=lote, numero_fisico=88, quantidade_regioes=1)
        regiao = pagina.regioes.filter(tipo_documental="termo_rescisao").first()
        if regiao is None:
            regiao = RegiaoDocumental.objects.create(
                lote=lote,
                pagina=pagina,
                tipo_documental="termo_rescisao",
                ordem=1,
                metodo_deteccao="teste",
                texto_regiao="termo",
            )
        return CampoExtraido.objects.create(
            regiao=regiao,
            esquema="termo_rescisao",
            chave=chave,
            rotulo=chave,
            valor_original=original,
            valor_normalizado=normalizado,
            numero_pagina=88,
            trecho_evidencia=original,
            metodo="ocr_totais_trct",
            estado_confianca="parcial",
            estado_revisao=EstadoCampo.PENDENTE,
        )
