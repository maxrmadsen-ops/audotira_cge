"""Três níveis de rastreio. Zero e ausência não herdam a caixa de outro trecho."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from aplicacao.laboratorio.apresentacao import nivel_de_rastreio
from aplicacao.laboratorio.localizacao import caixa_da_linha_rubrica


def _campo(**extras):
    base = dict(
        metodo="ocr_regiao",
        estado_confianca="evidencia_textual",
        valor_original="8.942,66",
        numero_pagina=88,
        evidencia_x=None,
        evidencia_y=None,
        evidencia_largura=None,
        evidencia_altura=None,
        localizacao_precisa=False,
        codigo="",
        descricao="",
        trecho_evidencia="",
    )
    base.update(extras)
    return SimpleNamespace(**base)


class NivelDeRastreioTests(SimpleTestCase):
    def test_tres_niveis_calculo_ausencia_e_zero(self):
        exato = _campo(
            localizacao_precisa=True,
            evidencia_x=0.9,
            evidencia_y=0.72,
            evidencia_largura=0.05,
            evidencia_altura=0.01,
        )
        aproximado = _campo(
            evidencia_x=0.0,
            evidencia_y=0.86,
            evidencia_largura=1.0,
            evidencia_altura=0.06,
        )
        so_pagina = _campo(valor_original="CRISTINA")
        calculado = _campo(
            metodo="calculo",
            estado_confianca="calculo",
            valor_original="R$ 7.811,51",
            localizacao_precisa=True,
            evidencia_x=0.1,
            evidencia_y=0.1,
            evidencia_largura=0.2,
            evidencia_altura=0.02,
        )
        ausente = _campo(
            valor_original="",
            estado_confianca="ausente",
            localizacao_precisa=True,
            evidencia_x=0.4,
            evidencia_y=0.4,
            evidencia_largura=0.1,
            evidencia_altura=0.02,
        )
        zero_sem_linha = _campo(
            codigo="51",
            descricao="Comissões",
            valor_original="0,00",
            trecho_evidencia="0,00",
            localizacao_precisa=True,
            evidencia_x=0.8,
            evidencia_y=0.4,
            evidencia_largura=0.05,
            evidencia_altura=0.02,
        )
        zero_na_linha = _campo(
            codigo="51",
            descricao="Comissões",
            valor_original="0,00",
            trecho_evidencia="51 Comissões 0,00",
            localizacao_precisa=True,
            evidencia_x=0.05,
            evidencia_y=0.4,
            evidencia_largura=0.4,
            evidencia_altura=0.02,
        )
        sem_origem = _campo(valor_original="", numero_pagina=0)
        self.assertEqual(nivel_de_rastreio(exato), "exata")
        self.assertEqual(nivel_de_rastreio(aproximado), "aproximada")
        self.assertEqual(nivel_de_rastreio(so_pagina), "pagina")
        self.assertEqual(nivel_de_rastreio(calculado), "calculo")
        self.assertEqual(nivel_de_rastreio(ausente, pagina_peca=88), "pagina")
        self.assertEqual(nivel_de_rastreio(zero_sem_linha, pagina_peca=88), "pagina")
        self.assertEqual(nivel_de_rastreio(zero_na_linha, pagina_peca=88), "exata")
        self.assertEqual(nivel_de_rastreio(sem_origem), "nenhuma")

    def test_zero_repetido_nao_escolhe_outra_linha(self):
        palavras = [
            {"texto": "50", "x": 0.05, "y": 0.40, "largura": 0.03, "altura": 0.02},
            {"texto": "Saldo", "x": 0.10, "y": 0.40, "largura": 0.08, "altura": 0.02},
            {"texto": "0,00", "x": 0.40, "y": 0.40, "largura": 0.05, "altura": 0.02},
            {"texto": "0,00", "x": 0.80, "y": 0.55, "largura": 0.05, "altura": 0.02},
        ]
        caixa = caixa_da_linha_rubrica(palavras, "50", "Saldo", "0,00", "0,00")
        self.assertIsNotNone(caixa)
        self.assertLess(caixa["x"], 0.2)
        self.assertIsNone(caixa_da_linha_rubrica(palavras, "", "", "0,00", "0,00"))
        self.assertIsNone(caixa_da_linha_rubrica(
            [{"texto": "0,00", "x": 0.8, "y": 0.5, "largura": 0.05, "altura": 0.02}],
            "52",
            "Gratificações",
            "0,00",
            "0,00",
        ))
