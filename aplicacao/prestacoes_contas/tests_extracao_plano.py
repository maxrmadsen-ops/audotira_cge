from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.classificacao import classificar
from aplicacao.documentos.codificacao import decodificar_uso_privado
from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.documentos.qualidade import avaliar_qualidade
from aplicacao.documentos.servico import _estruturar_termo
from aplicacao.instrumentos.models import TermoFomento
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano
from aplicacao.prestacoes_contas.extracao_plano import extrair_plano, estruturar_plano
from aplicacao.prestacoes_contas.models import ItemPlanoTrabalho, PlanoTrabalho, PrestacaoContas

Usuario = get_user_model()

TEXTO_PLANO = """
Listar Plano Trabalho
Proponente Entidade Sintetica Alfa
Transferência TR-SINT-001
Programa Transferência Programa Sintético
Unidade Gestora UG 000001 Unidade Sintética
Gestão 00001 Gestão Geral
Título Atendimento educacional sintético
Objeto/Finalidade Pagamento de despesas com profissionais de apoio
Objetivo/Resultados Esperados Ampliar o atendimento sintético
Descrição da Realidade Texto da realidade
Público Alvo 10 participantes
Capacidade Técnica Equipe local
Data Início Execução Data Término Execução 01/03/2024 31/12/2024
Situação Em execução
Data Situação 01/03/2024

Descrição Atendimento de apoio sintético
Data Início 01/03/2024 Data Fim 30/11/2024
Forma de Execução pagamento mensal
Parametros de Aferição Relatórios e registros
Adesão, Termo de Fomento e prestação de contas
Etapas

Material/Serviço/Obra Apoio pedagógico sintético
Classificação Orçamentária 30.00.00.00 Despesas Correntes
Tipo Despesa Serviço
Recurso Financeiro
Unidade Medida Un
Quantidade 2,00  150,00
Valor Unitário (R$)
Valor Total (R$) 300,00

Material/Serviço/Obra Recolhimento de INSS sintético
Classificação Orçamentária 30.00.00.00 Despesas Correntes
Tipo Despesa Serviço
Recurso Financeiro
Unidade Medida Guia
Quantidade 1,00  50,00
Valor Unitário (R$)
Valor Total (R$) 50,00

Cronograma
Ano 2024
Junho 200,00 0,00
Julho 150,00 0,00
"""


class TesteExtracaoPlano(TestCase):
    def test_texto_sintetico_fecha_itens_meta_e_cronograma(self):
        analise = extrair_plano(
            [
                {"numero_pagina": 1, "texto_extraido": TEXTO_PLANO.split("Descrição Atendimento")[0]},
                {"numero_pagina": 2, "texto_extraido": "Descrição Atendimento" + TEXTO_PLANO.split("Descrição Atendimento", 1)[1].split("Material/Serviço/Obra", 1)[0]},
                {"numero_pagina": 3, "texto_extraido": "Material/Serviço/Obra" + TEXTO_PLANO.split("Material/Serviço/Obra", 1)[1]},
            ]
        )
        self.assertEqual(analise["identificacao"]["transferencia"], "TR-SINT-001")
        self.assertEqual(analise["identificacao"]["inicio_execucao"], "01/03/2024")
        self.assertEqual(analise["identificacao"]["fim_execucao"], "31/12/2024")
        self.assertEqual(len(analise["metas"]), 1)
        self.assertIn("prestação de contas", analise["metas"][0]["etapas"])
        self.assertEqual(analise["metas"][0]["fim"], "30/11/2024")
        self.assertEqual(analise["metas"][0]["pagina"], 2)
        self.assertEqual(analise["itens"][0]["pagina"], 3)
        self.assertEqual(len(analise["itens"]), 2)
        self.assertEqual(sum(item["valor_total"] for item in analise["itens"]), Decimal("350.00"))
        self.assertEqual(analise["itens"][0]["natureza_sugerida"], "pessoal")
        self.assertEqual(analise["itens"][1]["natureza_sugerida"], "encargo")
        self.assertEqual(analise["itens"][0]["tipo_despesa"], "Serviço")
        self.assertTrue(analise["itens"][0]["trecho"])
        self.assertEqual(sum(Decimal(linha["repasse"]) for linha in analise["cronograma"]), Decimal("350.00"))

    def test_rotulos_colados_no_valor_continuam_legiveis(self):
        colado = (
            TEXTO_PLANO.replace("Quantidade ", "Quantidade")
            .replace("Tipo Despesa ", "Tipo Despesa")
            .replace("Unidade Medida ", "Unidade Medida")
            .replace("Data Início ", "Data Início")
            .replace("Data Fim ", "Data Fim")
            .replace("Ano ", "Ano")
        )
        analise = extrair_plano([{"numero_pagina": 1, "texto_extraido": colado}])
        self.assertEqual(len(analise["itens"]), 2)
        self.assertEqual(analise["itens"][0]["tipo_despesa"], "Serviço")
        self.assertEqual(analise["itens"][0]["unidade"], "Un")
        self.assertEqual(sum(Decimal(linha["repasse"]) for linha in analise["cronograma"] if linha["repasse"]), Decimal("350.00"))

    def test_fonte_de_uso_privado_volta_a_texto_e_nao_pede_ocr(self):
        codificado = "".join(chr(ord(caractere) + 0xF000) if ord(caractere) < 256 else caractere for caractere in TEXTO_PLANO)
        legivel, recuperado = decodificar_uso_privado(codificado)
        self.assertTrue(recuperado)
        self.assertIn("Listar Plano Trabalho", legivel)
        _qualidade, pede_ocr = avaliar_qualidade(legivel)
        self.assertFalse(pede_ocr)
        sugestao = classificar("relatorio.pdf", legivel)
        self.assertEqual(sugestao["tipo"], TipoDocumento.PLANO_TRABALHO)

    def test_plano_nao_cria_termo_e_so_entra_no_previsto_depois_da_revisao(self):
        usuario = Usuario.objects.create_user(
            username="auditor-plano",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.AUDITOR,
        )
        prestacao = PrestacaoContas.objects.create(numero_processo="PROC-PLANO-SINT", criado_por=usuario)
        documento = Documento.objects.create(
            prestacao_contas=prestacao,
            nome_original="plano-sintetico.pdf",
            nome_armazenado="plano-sintetico.pdf",
            tipo_documento=TipoDocumento.PLANO_TRABALHO,
            criado_por=usuario,
        )
        PaginaDocumento.objects.create(
            documento=documento,
            numero_pagina=1,
            texto_extraido=TEXTO_PLANO,
            metodo_extracao=MetodoExtracao.NATIVO,
            qualidade_extracao=QualidadeExtracao.SUFICIENTE,
            quantidade_caracteres=len(TEXTO_PLANO),
        )
        _estruturar_termo(documento)
        self.assertFalse(TermoFomento.objects.filter(documento=documento).exists())
        with patch("aplicacao.documentos.armazenamento.ler_arquivo", return_value="arquivo-inexistente.pdf"):
            estruturar_plano(documento)
        plano = PlanoTrabalho.objects.get(prestacao=prestacao, documento=documento)
        self.assertEqual(plano.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.assertEqual(plano.itens.count(), 2)
        self.assertTrue(all(item.status_revisao == StatusRevisaoPlano.AGUARDANDO for item in plano.itens.all()))
        self.assertIsNone(prestacao.valor_previsto)
        self.assertEqual(plano.valor_extraido, Decimal("350.00"))
        item = plano.itens.order_by("ordem").first()
        self.client.force_login(usuario)
        resposta = self.client.post(
            reverse("prestacoes_contas:revisao_plano", kwargs={"pk": prestacao.pk, "plano_pk": plano.pk}),
            {"acao": "confirmar_item", "item_id": item.pk},
        )
        self.assertEqual(resposta.status_code, 302)
        item.refresh_from_db()
        outro = plano.itens.exclude(pk=item.pk).get()
        self.assertEqual(item.status_revisao, StatusRevisaoPlano.CONFIRMADO)
        self.assertEqual(item.revisado_por_id, usuario.pk)
        self.assertEqual(outro.status_revisao, StatusRevisaoPlano.AGUARDANDO)
        self.assertEqual(PrestacaoContas.objects.get(pk=prestacao.pk).valor_previsto, item.valor_previsto)
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
                detalhes__acao="confirmar_item",
                detalhes__item=item.pk,
            ).exists()
        )
        with patch("aplicacao.documentos.armazenamento.ler_arquivo", return_value="arquivo-inexistente.pdf"):
            estruturar_plano(documento)
        self.assertEqual(ItemPlanoTrabalho.objects.filter(plano=plano).count(), 2)
        item.refresh_from_db()
        self.assertEqual(item.status_revisao, StatusRevisaoPlano.CONFIRMADO)
