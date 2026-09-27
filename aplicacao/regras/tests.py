from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from aplicacao.documentos.escolhas import MetodoExtracao, OrigemDocumento, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.entidades.models import Entidade, Fornecedor
from aplicacao.normas.escolhas import SituacaoNorma, StatusProcessamentoNorma, TipoNorma
from aplicacao.normas.models import Norma
from aplicacao.prestacoes_contas.escolhas import TipoDocumentoFiscal, TipoInstrumento, TipoMovimentacao
from aplicacao.prestacoes_contas.models import (
    Despesa,
    DocumentoFiscal,
    Instrumento,
    ItemPlanoTrabalho,
    MovimentacaoBancaria,
    Pagamento,
    PlanoTrabalho,
    PrestacaoContas,
)
from aplicacao.regras.catalogo import DependenciaCircular, carregar_matriz, sincronizar_catalogo, validar_grafo
from aplicacao.regras.classificacao import CLASSIFICACAO as CLASSIFICACAO_TECNICA
from aplicacao.regras.escolhas import (
    CONCLUSOES_VEDADAS,
    FONTE_EXCLUIDA_TESTE_CEGO,
    RESULTADO_SEMANTICO,
    SINTESE_NAO_CONCLUSIVA,
    StatusAnalise,
    StatusTecnico,
)
from aplicacao.regras.executores import ExecutorContexto
from aplicacao.regras.models import ExecucaoRegra, ReferenciaExecucao, RegraAnalise
from aplicacao.regras.motor import criar_analise, executar_analise
from aplicacao.usuarios.models import Usuario

SEGREDO = "SEGREDO_ANALISE_PREVIA_UNICO"


def executar(prestacao, usuario=None, teste_cego=False):
    analise = criar_analise(prestacao=prestacao, usuario=usuario, modo_teste_cego=teste_cego)
    executar_analise(analise.pk)
    analise.refresh_from_db()
    return analise


def resultado(analise, codigo):
    return analise.execucoes.select_related("regra").get(regra__codigo=codigo)


class TesteCatalogoRegras(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_catalogo()
        sincronizar_catalogo()

    def test_catalogo_tem_89_regras_19_categorias_e_campos_originais(self):
        matriz = carregar_matriz()
        self.assertEqual(len(matriz["regras"]), 89)
        self.assertEqual(len({item["ID"] for item in matriz["regras"]}), 89)
        self.assertEqual(len({item["Categoria"] for item in matriz["regras"]}), 19)
        self.assertEqual(set(CLASSIFICACAO_TECNICA), {item["ID"] for item in matriz["regras"]})
        ativas = RegraAnalise.objects.filter(ativa=True)
        self.assertEqual(ativas.count(), 89)
        self.assertEqual(RegraAnalise.objects.count(), 89)
        for regra in ativas:
            self.assertTrue(regra.categoria)
            self.assertTrue(regra.descricao_original)
            self.assertTrue(regra.resultados_possiveis)
            self.assertTrue(regra.evidencia_obrigatoria)
            self.assertTrue(regra.tratamento_analista)
            self.assertEqual(regra.conteudo_original["ID"], regra.codigo)
            self.assertEqual(regra.titulo, regra.conteudo_original["Regra de análise"])

    def test_efe_preserva_o_resultado_da_matriz(self):
        regra = RegraAnalise.objects.get(codigo="EFE-001", ativa=True)
        self.assertEqual(regra.resultados_possiveis, "NÃO REALIZADA – ESCOPO DA V1")
        self.assertEqual(regra.tipo_execucao, "fora_escopo_v1")

    def test_dependencia_circular_e_rejeitada(self):
        with self.assertRaises(DependenciaCircular):
            validar_grafo({"CONT-002": ["CONT-001"], "CONT-001": ["CONT-002"]})

    def test_cont_002_depende_de_cont_001(self):
        dependencia = RegraAnalise.objects.get(codigo="CONT-002", ativa=True).dependencias.get()
        self.assertEqual(dependencia.codigo_requisito, "CONT-001")
        self.assertEqual(dependencia.tipo, "condiciona")


class TesteMotorRegras(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_catalogo()
        cls.usuario = Usuario.objects.create_user(
            username="analista-regras",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
        cls.consulta = Usuario.objects.create_user(
            username="consulta-regras",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.CONSULTA,
        )

    def prestacao(self, numero="PROC-REGRAS"):
        concedente = Entidade.objects.create(nome=f"Concedente {numero}", tipo=Entidade.Tipo.CONCEDENTE, demonstracao=True)
        beneficiario = Entidade.objects.create(
            nome=f"Beneficiário {numero}",
            tipo=Entidade.Tipo.BENEFICIARIO,
            demonstracao=True,
        )
        return PrestacaoContas.objects.create(
            numero_processo=numero,
            concedente=concedente,
            beneficiario=beneficiario,
            objeto="Objeto fictício de teste",
            valor_total=Decimal("1000.00"),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 31),
            demonstracao=True,
        )

    def instrumento(self, prestacao, inicio=date(2024, 1, 1), fim=date(2024, 12, 31), valor=Decimal("1000.00")):
        return Instrumento.objects.create(
            prestacao=prestacao,
            numero="TF-TESTE-1",
            tipo=TipoInstrumento.TERMO_FOMENTO,
            data_assinatura=inicio,
            vigencia_inicio=inicio,
            vigencia_fim=fim,
            valor=valor,
            objeto=prestacao.objeto,
            principal=True,
            demonstracao=True,
        )

    def despesa_com_valores(self, prestacao, documentado, pago, emissao, cnpj_fornecedor="", identificador_pagamento=""):
        entidade = Entidade.objects.create(
            nome=f"Fornecedor {documentado}-{pago}",
            tipo=Entidade.Tipo.FORNECEDOR,
            cnpj=cnpj_fornecedor,
            demonstracao=True,
        )
        fornecedor = Fornecedor.objects.create(entidade=entidade, demonstracao=True)
        despesa = Despesa.objects.create(
            prestacao=prestacao,
            fornecedor=fornecedor,
            descricao="Despesa de teste",
            valor=documentado,
            data=emissao,
            demonstracao=True,
        )
        fiscal = DocumentoFiscal.objects.create(
            prestacao=prestacao,
            emitente=fornecedor,
            tipo=TipoDocumentoFiscal.NOTA_FISCAL,
            numero="NF-1",
            data_emissao=emissao,
            valor=documentado,
            demonstracao=True,
        )
        fiscal.despesas.add(despesa)
        pagamento = Pagamento.objects.create(
            prestacao=prestacao,
            data=emissao,
            valor=pago,
            identificador=identificador_pagamento,
            demonstracao=True,
        )
        pagamento.despesas.add(despesa)
        pagamento.documentos_fiscais.add(fiscal)
        movimento = MovimentacaoBancaria.objects.create(
            prestacao=prestacao,
            data=emissao,
            valor=pago,
            tipo=TipoMovimentacao.DEBITO,
            identificador=identificador_pagamento,
            historico="Débito de teste",
            demonstracao=True,
        )
        movimento.pagamentos.add(pagamento)
        return despesa

    def test_fin_003_calcula_diferenca_em_decimal(self):
        prestacao = self.prestacao("PROC-FIN-003")
        self.instrumento(prestacao)
        self.despesa_com_valores(prestacao, Decimal("1000.00"), Decimal("950.00"), date(2024, 3, 10))
        analise = executar(prestacao, self.usuario)
        item = resultado(analise, "FIN-003")
        self.assertEqual(item.resultado_funcional, "DIVERGÊNCIA")
        self.assertEqual(item.status_tecnico, StatusTecnico.DIVERGENCIA)
        diferenca = item.calculos.get(operacao="diferenca")
        percentual = item.calculos.get(operacao="percentual")
        self.assertEqual(diferenca.resultado, Decimal("50.00"))
        self.assertEqual(percentual.resultado, Decimal("5.00"))
        self.assertEqual(diferenca.unidade, "BRL")
        self.assertIsInstance(diferenca.resultado, Decimal)
        self.assertNotIn(analise.sintese, CONCLUSOES_VEDADAS)

    def test_ausencia_nao_vira_divergencia(self):
        prestacao = self.prestacao("PROC-AUSENCIA")
        analise = executar(prestacao, self.usuario)
        for codigo in ("FIN-003", "DES-003", "DES-004", "PAG-002", "PAG-003", "VED-009", "PT-003", "PT-004", "DEV-001", "DEV-002", "PRE-001", "CTX-004"):
            item = resultado(analise, codigo)
            self.assertIn(item.resultado_funcional, {"NÃO VERIFICÁVEL", "NÃO LOCALIZADO"})
            self.assertNotEqual(item.status_tecnico, StatusTecnico.DIVERGENCIA)
            self.assertNotIn(item.resultado_funcional, CONCLUSOES_VEDADAS)
        self.assertEqual(analise.sintese, SINTESE_NAO_CONCLUSIVA)
        self.assertEqual(analise.status, StatusAnalise.AGUARDANDO_VALIDACAO)
        self.assertEqual(resultado(analise, "SYS-003").resultado_funcional, "PENDENTE DE VALIDAÇÃO")
        self.assertEqual(resultado(analise, "SYS-001").resultado_funcional, "NÃO CONCLUSIVO")

    def test_ved_009_respeita_a_data_de_emissao_e_a_vigencia(self):
        dentro = self.prestacao("PROC-VED-DENTRO")
        self.instrumento(dentro)
        self.despesa_com_valores(dentro, Decimal("10.00"), Decimal("10.00"), date(2024, 6, 1))
        self.assertEqual(resultado(executar(dentro), "VED-009").resultado_funcional, "CONFORME")

        fora = self.prestacao("PROC-VED-FORA")
        self.instrumento(fora)
        self.despesa_com_valores(fora, Decimal("10.00"), Decimal("10.00"), date(2023, 6, 1))
        item = resultado(executar(fora), "VED-009")
        self.assertEqual(item.resultado_funcional, "FORA DA VIGÊNCIA")
        self.assertNotIn(item.resultado_funcional, CONCLUSOES_VEDADAS)

        sem_data = self.prestacao("PROC-VED-SEM")
        self.instrumento(sem_data)
        self.assertEqual(resultado(executar(sem_data), "VED-009").resultado_funcional, "NÃO VERIFICÁVEL")

    def test_identidade_prioriza_cnpj_e_nao_trata_nome_como_prova(self):
        conforme = self.prestacao("PROC-ID-OK")
        self.instrumento(conforme)
        cnpj = "11.222.333/0001-81"
        self.despesa_com_valores(conforme, Decimal("10.00"), Decimal("10.00"), date(2024, 2, 2), cnpj, "11222333000181")
        item = resultado(executar(conforme), "PAG-004")
        self.assertEqual(item.resultado_funcional, "CONFORME")
        self.assertEqual(item.entradas["metodo"], "cnpj")

        sem_id = self.prestacao("PROC-ID-NOME")
        self.instrumento(sem_id)
        self.despesa_com_valores(sem_id, Decimal("10.00"), Decimal("10.00"), date(2024, 2, 2), "", "")
        item = resultado(executar(sem_id), "FIN-001")
        self.assertEqual(item.resultado_funcional, "NÃO VERIFICÁVEL")
        self.assertIn("não comprovam identidade", item.limitacao)

    def test_ved_012_nao_infere_parentesco(self):
        prestacao = self.prestacao("PROC-VED-012")
        prestacao.beneficiario.nome = "Ana Silva"
        prestacao.beneficiario.save()
        self.instrumento(prestacao)
        self.despesa_com_valores(prestacao, Decimal("10.00"), Decimal("10.00"), date(2024, 2, 2))
        Despesa.objects.filter(prestacao=prestacao).update(descricao="Pagamento a João Silva")
        item = resultado(executar(prestacao), "VED-012")
        self.assertEqual(item.resultado_funcional, "NÃO VERIFICÁVEL")
        self.assertEqual(item.encaminhamento, "requer_analista")
        self.assertIn("parentesco", item.limitacao.casefold())
        self.assertNotEqual(item.status_tecnico, StatusTecnico.DIVERGENCIA)

    def test_regra_semantica_nao_conclui(self):
        prestacao = self.prestacao("PROC-SEM")
        self.instrumento(prestacao)
        item = resultado(executar(prestacao), "PT-002")
        self.assertEqual(item.resultado_funcional, RESULTADO_SEMANTICO)
        self.assertEqual(item.encaminhamento, "requer_ia")
        self.assertEqual(item.status_tecnico, StatusTecnico.NAO_EXECUTADA)
        self.assertEqual(resultado(executar(prestacao), "EFE-001").resultado_funcional, "NÃO REALIZADA – ESCOPO DA V1")

    def test_teste_cego_exclui_relatorio_com_analise_previa(self):
        prestacao = self.prestacao("PROC-CEGO")
        self.instrumento(prestacao)
        permitido = Documento.objects.create(
            prestacao_contas=prestacao,
            nome_original="Termo autorizado.pdf",
            nome_armazenado="termo-autorizado.pdf",
            tipo_documento=TipoDocumento.TERMO,
            origem=OrigemDocumento.DEMONSTRACAO,
            demonstracao=True,
        )
        bloqueado = Documento.objects.create(
            prestacao_contas=prestacao,
            nome_original="Relatório de prestação final com análise técnica.pdf",
            nome_armazenado="relatorio-bloqueado.pdf",
            tipo_documento=TipoDocumento.PRESTACAO_FINAL,
            subtipo_documento=FONTE_EXCLUIDA_TESTE_CEGO,
            origem=OrigemDocumento.DEMONSTRACAO,
            demonstracao=True,
        )
        PaginaDocumento.objects.create(
            documento=bloqueado,
            numero_pagina=1,
            texto_extraido=SEGREDO,
            metodo_extracao=MetodoExtracao.NATIVO,
            qualidade_extracao=QualidadeExtracao.SUFICIENTE,
        )
        analise = executar(prestacao, self.usuario, teste_cego=True)
        item = resultado(analise, "DOC-009")
        self.assertEqual(item.resultado_funcional, "EXCLUÍDO DO ESCOPO")
        self.assertEqual(analise.documentos_excluidos[0]["documento_id"], bloqueado.id)
        self.assertEqual(analise.documentos_excluidos[0]["motivo"], FONTE_EXCLUIDA_TESTE_CEGO)
        referencias = ReferenciaExecucao.objects.filter(execucao__analise=analise)
        self.assertTrue(referencias.filter(documento=bloqueado, papel_na_regra=FONTE_EXCLUIDA_TESTE_CEGO).exists())
        self.assertFalse(referencias.filter(documento=bloqueado).exclude(papel_na_regra=FONTE_EXCLUIDA_TESTE_CEGO).exists())
        self.assertTrue(referencias.filter(documento=permitido, papel_na_regra="documento_localizado").exists())
        semantica = resultado(analise, "PT-002")
        self.assertNotIn(bloqueado.id, semantica.entradas["fontes_autorizadas"])
        self.assertIn(permitido.id, semantica.entradas["fontes_autorizadas"])
        textos = " ".join(referencias.values_list("trecho", flat=True))
        textos += " ".join(analise.execucoes.values_list("limitacao", flat=True))
        textos += str(list(analise.execucoes.values_list("entradas", flat=True)))
        self.assertNotIn(SEGREDO, textos)

    def test_vigencia_normativa_nao_usa_norma_fora_do_periodo(self):
        prestacao = self.prestacao("PROC-NORMA")
        self.instrumento(prestacao, inicio=date(2020, 6, 1), fim=date(2020, 12, 31))
        historica = Norma.objects.create(
            tipo_norma=TipoNorma.LEI,
            numero="100",
            ano=2018,
            titulo="Norma histórica de teste",
            inicio_vigencia=date(2018, 1, 1),
            fim_vigencia=date(2021, 12, 31),
            situacao=SituacaoNorma.VIGENTE,
            status_processamento=StatusProcessamentoNorma.DISPONIVEL,
        )
        posterior = Norma.objects.create(
            tipo_norma=TipoNorma.INSTRUCAO_NORMATIVA,
            numero="200",
            ano=2022,
            titulo="Norma posterior de teste",
            inicio_vigencia=date(2022, 3, 4),
            situacao=SituacaoNorma.VIGENTE,
            status_processamento=StatusProcessamentoNorma.DISPONIVEL,
        )
        item = resultado(executar(prestacao), "CTX-005")
        self.assertEqual(item.resultado_funcional, "NORMAS IDENTIFICADAS")
        identificadores = set(item.referencias.filter(tipo_fonte="norma").values_list("identificador", flat=True))
        self.assertIn(str(historica.id), identificadores)
        self.assertNotIn(str(posterior.id), identificadores)

    def test_execucao_permanece_na_versao_da_regra(self):
        prestacao = self.prestacao("PROC-VERSAO")
        self.instrumento(prestacao)
        analise = executar(prestacao)
        execucao = resultado(analise, "CTX-001")
        versao_antiga = execucao.regra
        titulo = execucao.snapshot["titulo"]
        versao_antiga.ativa = False
        versao_antiga.save(update_fields=["ativa"])
        RegraAnalise.objects.create(
            codigo=versao_antiga.codigo,
            versao=versao_antiga.versao + 1,
            categoria=versao_antiga.categoria,
            titulo="TITULO_NOVO",
            descricao_original=versao_antiga.descricao_original,
            tipo_execucao=versao_antiga.tipo_execucao,
            capacidade=versao_antiga.capacidade,
            executor=versao_antiga.executor,
            ativa=True,
            ordem=versao_antiga.ordem,
        )
        execucao.refresh_from_db()
        self.assertEqual(execucao.regra_id, versao_antiga.id)
        self.assertEqual(execucao.snapshot["titulo"], titulo)
        self.assertNotEqual(execucao.snapshot["titulo"], "TITULO_NOVO")

    def test_falha_de_uma_regra_nao_aborta_a_rodada(self):
        prestacao = self.prestacao("PROC-ERRO")
        self.instrumento(prestacao)
        original = ExecutorContexto.executar

        def falha(self, regra, contexto):
            if regra.codigo == "CTX-001":
                raise RuntimeError("falha isolada de teste")
            return original(self, regra, contexto)

        with patch.object(ExecutorContexto, "executar", falha):
            analise = executar(prestacao)
        self.assertEqual(resultado(analise, "CTX-001").status_tecnico, StatusTecnico.ERRO)
        self.assertEqual(resultado(analise, "CTX-002").resultado_funcional, "IDENTIFICADO")
        self.assertEqual(analise.status, StatusAnalise.AGUARDANDO_VALIDACAO)
        self.assertGreater(analise.erros, 0)
        self.assertEqual(analise.sintese, SINTESE_NAO_CONCLUSIVA)

    def test_cont_002_so_segue_se_houver_contrapartida_financeira(self):
        prestacao = self.prestacao("PROC-CONT")
        self.instrumento(prestacao)
        from aplicacao.prestacoes_contas.models import Contrapartida

        Contrapartida.objects.create(prestacao=prestacao, descricao="Contrapartida em bens de teste", valor=Decimal("20.00"), demonstracao=True)
        analise = executar(prestacao)
        self.assertEqual(resultado(analise, "CONT-001").resultado_funcional, "EXISTE")
        self.assertEqual(resultado(analise, "CONT-002").status_tecnico, StatusTecnico.NAO_APLICAVEL)

    def test_interface_do_catalogo_e_da_analise(self):
        prestacao = self.prestacao("PROC-TELA")
        self.instrumento(prestacao)
        self.client.force_login(self.usuario)
        lista = self.client.get(reverse("regras:lista"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "FIN-003")
        self.assertContains(lista, "a conclusão cabe ao analista")
        detalhe = self.client.get(reverse("regras:detalhe", kwargs={"codigo": "DOC-001"}))
        self.assertContains(detalhe, "Fonte normativa indicada nas diretrizes")
        self.assertContains(detalhe, "Resultado possível")
        self.assertContains(detalhe, "Evidência obrigatória")
        self.assertContains(detalhe, "Tratamento/Ação para o analista")
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.post(reverse("regras:executar", kwargs={"pk": prestacao.pk})).status_code, 403)
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("regras:executar", kwargs={"pk": prestacao.pk}), {"modo": "normal"})
        self.assertEqual(resposta.status_code, 302)
        analise = prestacao.execucoes_analise.get()
        self.assertEqual(analise.sintese, SINTESE_NAO_CONCLUSIVA)
        aba = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": prestacao.pk}), {"aba": "analise"})
        self.assertContains(aba, "NÃO CONCLUSIVO")
        self.assertContains(aba, "PENDENTE DE VALIDAÇÃO")
        self.assertNotContains(aba, ">REGULAR<")
        self.assertNotContains(aba, ">APROVADO<")

    def test_comando_de_carga_e_idempotente(self):
        antes = RegraAnalise.objects.count()
        call_command("carregar_regras_cge")
        self.assertEqual(RegraAnalise.objects.count(), antes)
        self.assertEqual(CLASSIFICACAO_TECNICA["FIN-003"]["capacidade"], "automatica")
        self.assertFalse(ExecucaoRegra.objects.filter(resultado_funcional__in=CONCLUSOES_VEDADAS).exists())
