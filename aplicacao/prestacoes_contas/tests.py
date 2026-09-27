from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.entidades.models import Entidade, Fornecedor, Funcionario, Pessoa
from aplicacao.prestacoes_contas.campos import DinheiroField
from aplicacao.prestacoes_contas.escolhas import TipoPrestacaoParcial
from aplicacao.prestacoes_contas.linha_do_tempo import montar_linha_do_tempo
from aplicacao.prestacoes_contas.models import (
    Contrapartida,
    Despesa,
    Devolucao,
    DocumentoFiscal,
    Instrumento,
    ItemPlanoTrabalho,
    Meta,
    MovimentacaoBancaria,
    Pagamento,
    PlanoTrabalho,
    PrestacaoContas,
    PrestacaoParcial,
)

Usuario = get_user_model()


class BaseDominio(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username="admin-dom",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ADMINISTRADOR,
        )
        self.analista = Usuario.objects.create_user(
            username="analista-dom",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        self.consulta = Usuario.objects.create_user(
            username="consulta-dom",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.CONSULTA,
        )

    def prestacao(self, numero="PROC-DOM-1", **extras):
        return PrestacaoContas.objects.create(numero_processo=numero, criado_por=self.administrador, **extras)


class TesteEntidades(BaseDominio):
    def test_entidade_pessoa_funcionario_e_fornecedor(self):
        orgao = Entidade.objects.create(nome="Órgão Sintético", tipo=Entidade.Tipo.CONCEDENTE)
        pessoa = Pessoa.objects.create(nome="Ana Sintética")
        vinculo = Funcionario.objects.create(pessoa=pessoa, entidade=orgao, cargo="Analista")
        papel = Fornecedor.objects.create(entidade=orgao, ramo="Serviços")
        self.assertEqual(vinculo.pessoa.nome, "Ana Sintética")
        self.assertEqual(papel.entidade_id, orgao.pk)
        self.assertNotIn("cpf", {campo.name for campo in Funcionario._meta.fields})

    def test_cnpj_e_cpf_unicos_somente_quando_informados(self):
        Entidade.objects.create(nome="Um", cnpj="")
        Entidade.objects.create(nome="Dois", cnpj="")
        Pessoa.objects.create(nome="Sem documento")
        Pessoa.objects.create(nome="Outra sem documento")
        Entidade.objects.create(nome="Com CNPJ", cnpj="00.000.000/0001-91")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Entidade.objects.create(nome="CNPJ repetido", cnpj="00.000.000/0001-91")

    def test_remuneracao_negativa_e_datas_invertidas_sao_recusadas(self):
        pessoa = Pessoa.objects.create(nome="Pessoa")
        entidade = Entidade.objects.create(nome="Entidade")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Funcionario.objects.create(pessoa=pessoa, entidade=entidade, remuneracao_base=Decimal("-1.00"))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Funcionario.objects.create(
                    pessoa=pessoa,
                    entidade=entidade,
                    data_admissao=date(2024, 5, 2),
                    data_desligamento=date(2024, 5, 1),
                )


class TestePrestacaoEInstrumento(BaseDominio):
    def test_prestacao_incompleta_e_instrumento_normalizado(self):
        prestacao = self.prestacao()
        self.assertIsNone(prestacao.concedente)
        self.assertIsNone(prestacao.valor_total)
        self.assertIsNone(prestacao.valor_previsto)
        self.assertIsNone(prestacao.valor_executado)
        self.assertIsNone(prestacao.diferenca_previsto_executado)
        Instrumento.objects.create(
            prestacao=prestacao,
            numero="TF-1",
            tipo="termo_fomento",
            valor=Decimal("1500.50"),
            principal=True,
        )
        prestacao = PrestacaoContas.objects.get(pk=prestacao.pk)
        self.assertEqual(prestacao.numero_instrumento, "TF-1")
        self.assertEqual(prestacao.tipo_instrumento, "Termo de fomento")
        self.assertEqual(prestacao.valor_previsto, Decimal("1500.50"))
        self.assertIsInstance(prestacao.valor_previsto, Decimal)

    def test_dinheiro_nao_usa_float_e_valor_negativo_e_recusado(self):
        campo = PrestacaoContas._meta.get_field("valor_total")
        self.assertIsInstance(campo, DinheiroField)
        self.assertEqual(campo.decimal_places, 2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.prestacao(numero="PROC-NEG", valor_total=Decimal("-0.01"))

    def test_datas_invertidas_sao_recusadas(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.prestacao(numero="PROC-DATA", data_inicio=date(2024, 2, 2), data_fim=date(2024, 2, 1))


class TestePlanoEParciais(BaseDominio):
    def test_plano_itens_metas_e_previsto_contra_executado(self):
        prestacao = self.prestacao(valor_total=Decimal("999.00"))
        plano = PlanoTrabalho.objects.create(prestacao=prestacao, titulo="Plano sintético", versao=1)
        item = ItemPlanoTrabalho.objects.create(
            plano=plano,
            descricao="Item previsto",
            quantidade=Decimal("2.000"),
            valor_previsto=Decimal("100.00"),
            natureza="material",
        )
        Meta.objects.create(plano=plano, descricao="Meta sintética", quantidade_prevista=Decimal("2.000"))
        Despesa.objects.create(prestacao=prestacao, item_plano=item, valor=Decimal("40.00"), descricao="Parcial")
        self.assertEqual(plano.valor_previsto, Decimal("100.00"))
        self.assertEqual(item.valor_realizado, Decimal("40.00"))
        self.assertEqual(prestacao.valor_previsto, Decimal("100.00"))
        self.assertEqual(prestacao.valor_executado, Decimal("40.00"))
        self.assertEqual(prestacao.diferenca_previsto_executado, Decimal("60.00"))

    def test_parciais_ordenadas_sem_quantidade_fixa(self):
        prestacao = self.prestacao()
        PrestacaoParcial.objects.create(prestacao=prestacao, numero_ordem=2, tipo=TipoPrestacaoParcial.FINAL)
        PrestacaoParcial.objects.create(prestacao=prestacao, numero_ordem=1, tipo=TipoPrestacaoParcial.PARCIAL)
        PrestacaoParcial.objects.create(prestacao=prestacao, numero_ordem=3, tipo=TipoPrestacaoParcial.PARCIAL)
        rotulos = [str(parcial) for parcial in prestacao.parciais.all()]
        self.assertEqual(rotulos, ["Prestação parcial 01", "Prestação final", "Prestação parcial 03"])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrestacaoParcial.objects.create(prestacao=prestacao, numero_ordem=1)


class TesteExecucaoFinanceira(BaseDominio):
    def test_cruzamento_flexivel_entre_despesa_documento_pagamento_e_movimento(self):
        prestacao = self.prestacao()
        parcial = PrestacaoParcial.objects.create(prestacao=prestacao, numero_ordem=1)
        despesa = Despesa.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            descricao="Despesa",
            valor=Decimal("10.00"),
        )
        nota = DocumentoFiscal.objects.create(prestacao=prestacao, numero="1", valor=Decimal("10.00"))
        recibo = DocumentoFiscal.objects.create(prestacao=prestacao, numero="2", valor=None)
        nota.despesas.add(despesa)
        recibo.despesas.add(despesa)
        primeiro = Pagamento.objects.create(prestacao=prestacao, valor=Decimal("6.00"), identificador="P1")
        segundo = Pagamento.objects.create(prestacao=prestacao, valor=Decimal("4.00"), identificador="P2")
        primeiro.despesas.add(despesa)
        segundo.despesas.add(despesa)
        primeiro.documentos_fiscais.add(nota)
        movimento = MovimentacaoBancaria.objects.create(prestacao=prestacao, valor=Decimal("6.00"), tipo="debito")
        movimento.pagamentos.add(primeiro, segundo)
        Contrapartida.objects.create(prestacao=prestacao, valor=None, descricao="")
        Devolucao.objects.create(prestacao=prestacao, valor=Decimal("1.00"), motivo="")
        self.assertEqual(despesa.documentos_fiscais.count(), 2)
        self.assertEqual(despesa.pagamentos.count(), 2)
        self.assertEqual(movimento.pagamentos.count(), 2)
        self.assertIsNone(prestacao.contrapartidas.get().valor)
        self.assertEqual(prestacao.devolucoes.get().valor, Decimal("1.00"))

    def test_valor_de_documento_negativo_e_recusado(self):
        prestacao = self.prestacao()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentoFiscal.objects.create(prestacao=prestacao, valor=Decimal("-5"))


class TesteLinhaDoTempo(BaseDominio):
    def test_marcos_datados_precedem_os_sem_data(self):
        prestacao = self.prestacao()
        Instrumento.objects.create(prestacao=prestacao, numero="TF-9", data_assinatura=date(2024, 1, 10))
        PlanoTrabalho.objects.create(prestacao=prestacao, titulo="Plano", vigencia_inicio=date(2024, 1, 1))
        PrestacaoParcial.objects.create(
            prestacao=prestacao,
            numero_ordem=1,
            periodo_inicio=date(2024, 2, 1),
            descricao="Primeira",
        )
        PrestacaoParcial.objects.create(prestacao=prestacao, numero_ordem=2, tipo=TipoPrestacaoParcial.FINAL)
        Pagamento.objects.create(prestacao=prestacao, data=date(2024, 3, 1), identificador="PG")
        Devolucao.objects.create(prestacao=prestacao, data=date(2024, 4, 1), motivo="Saldo")
        marcos = montar_linha_do_tempo(prestacao)
        tipos = [marco.tipo for marco in marcos]
        self.assertEqual(
            tipos,
            ["Plano de trabalho", "Instrumento", "Prestação", "Pagamento", "Devolução", "Prestação"],
        )
        self.assertIsNone(marcos[-1].data)
        self.assertEqual(marcos[-1].titulo, "Prestação final")


class TesteInterfaceEPermissoes(BaseDominio):
    def test_consulta_le_e_nao_altera(self):
        prestacao = self.prestacao(objeto="Objeto visível")
        self.client.force_login(self.consulta)
        lista = self.client.get(reverse("prestacoes_contas:lista"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, prestacao.numero_processo)
        self.assertNotContains(lista, "Nova prestação")
        detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}))
        self.assertContains(detalhe, "Visão Geral")
        self.assertContains(detalhe, "Linha do Tempo")
        self.assertContains(detalhe, "FinOps")
        self.assertEqual(self.client.get(reverse("prestacoes_contas:nova")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("prestacoes_contas:incluir_despesa", kwargs={"pk": prestacao.pk}),
                {"descricao": "não deve gravar"},
            ).status_code,
            403,
        )
        self.assertFalse(prestacao.despesas.exists())

    def test_analista_cadastra_e_gera_auditoria_sem_valor(self):
        self.client.force_login(self.analista)
        resposta = self.client.post(
            reverse("prestacoes_contas:nova"),
            {
                "numero_processo": "PROC-FORM-1",
                "objeto": "Objeto de formulário",
                "situacao": "em_elaboracao",
                "fase": "pactuacao",
                "nome_concedente": "Concedente Formulário",
                "nome_beneficiario": "Beneficiário Formulário",
                "numero_instrumento": "INST-FORM-1",
                "tipo_instrumento": "convenio",
            },
        )
        prestacao = PrestacaoContas.objects.get(numero_processo="PROC-FORM-1")
        self.assertRedirects(resposta, reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}))
        self.assertEqual(prestacao.concedente.nome, "Concedente Formulário")
        self.assertEqual(prestacao.numero_instrumento, "INST-FORM-1")
        self.assertEqual(prestacao.criado_por, self.analista)
        registro = RegistroAuditoria.objects.get(evento=RegistroAuditoria.Evento.CRIACAO)
        self.assertEqual(registro.usuario, self.analista)
        self.assertEqual(registro.detalhes["entidade"], "prestacoes_contas.PrestacaoContas")
        self.assertEqual(registro.detalhes["identificador"], str(prestacao.pk))
        self.assertNotIn("valor_total", registro.detalhes)
        self.assertNotIn("objeto", registro.detalhes)

    def test_filtro_e_paginacao(self):
        self.prestacao(numero="PROC-A", objeto="alfa")
        self.prestacao(numero="PROC-B", objeto="beta")
        for indice in range(20):
            self.prestacao(numero=f"PROC-PAG-{indice:02d}")
        self.client.force_login(self.consulta)
        filtrada = self.client.get(reverse("prestacoes_contas:lista"), {"q": "alfa"})
        self.assertContains(filtrada, "PROC-A")
        self.assertNotContains(filtrada, "PROC-B")
        pagina = self.client.get(reverse("prestacoes_contas:lista"), {"page": 2})
        self.assertContains(pagina, "Página 2")

    def test_api_somente_leitura_e_autenticada(self):
        self.prestacao(numero="PROC-API")
        self.assertIn(self.client.get("/api/prestacoes/").status_code, {401, 403})
        self.client.force_login(self.consulta)
        resposta = self.client.get("/api/prestacoes/")
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        itens = corpo["results"] if isinstance(corpo, dict) else corpo
        self.assertEqual(itens[0]["numero_processo"], "PROC-API")
        self.assertEqual(self.client.post("/api/prestacoes/", {}).status_code, 405)


class TesteCenarioDemonstracao(BaseDominio):
    def test_comando_e_idempotente_e_nao_usa_o_caso_real(self):
        call_command("carregar_cenario_demonstracao")
        call_command("carregar_cenario_demonstracao")
        prestacao = PrestacaoContas.objects.get(numero_processo="DEMO-2024-001")
        self.assertTrue(prestacao.demonstracao)
        self.assertEqual(prestacao.parciais.count(), 2)
        self.assertEqual(prestacao.valor_previsto, Decimal("5800.00"))
        self.assertEqual(prestacao.valor_executado, Decimal("1910.00"))
        self.assertEqual(prestacao.despesas.count(), 5)
        self.assertTrue(prestacao.despesas.get(descricao="Compra fictícia de material").documentos_fiscais.exists())
        self.assertTrue(prestacao.pagamentos.get(identificador="PIX-DEMO-1001").movimentacoes.exists())
        self.assertTrue(prestacao.despesas.filter(descricao="DEMO-REGRAS dados insuficientes").exists())
        self.assertEqual(Funcionario.objects.filter(entidade=prestacao.beneficiario).count(), 1)
        self.client.force_login(self.consulta)
        detalhe = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}))
        self.assertContains(detalhe, "Dados de demonstração")
        self.assertNotContains(detalhe, "2022TR000929")
        self.assertEqual(PrestacaoContas.objects.filter(numero_processo="DEMO-2024-001").count(), 1)
