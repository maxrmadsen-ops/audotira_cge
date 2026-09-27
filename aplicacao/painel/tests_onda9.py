"""Testes da Onda 9. Não chamam provedor real."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aplicacao.achados.escolhas import Criticidade, MetodoObtencao, StatusAchado, TipoEvidencia
from aplicacao.achados.models import Achado, Evidencia, RevisaoAchado
from aplicacao.avaliacao.escolhas import ClassificacaoCorrespondencia, CriticidadeReferencia, ModoGroundTruth
from aplicacao.avaliacao.models import (
    AvaliacaoInteligenciaArtificial,
    CorrespondenciaAchado,
    GroundTruthAchado,
    GroundTruthPrestacao,
)
from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.inteligencia_artificial.escolhas import ProvedorIA, StatusUso
from aplicacao.inteligencia_artificial.models import ModeloInteligenciaArtificial, PrecoModeloInteligenciaArtificial, UsoInteligenciaArtificial
from aplicacao.normas.escolhas import SituacaoNorma, TipoNorma
from aplicacao.normas.models import Norma
from aplicacao.painel.consultas.filtros import FiltrosPainel
from aplicacao.painel.consultas.finops import custo_da_chamada, montar_finops
from aplicacao.painel.consultas.tipos import NAO_DISPONIVEL, SEM_HISTORICO
from aplicacao.regras.escolhas import FONTE_EXCLUIDA_TESTE_CEGO, CapacidadeExecucao, StatusTecnico, TipoExecucaoTecnica
from aplicacao.regras.models import ExecucaoAnalise, ExecucaoRegra, RegraAnalise

Usuario = get_user_model()


class TestePainelOnda9(TestCase):
    def setUp(self):
        self.consulta = Usuario.objects.create_user(username="consulta-o9", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.CONSULTA)
        self.analista = Usuario.objects.create_user(username="analista-o9", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ANALISTA)
        self.auditor = Usuario.objects.create_user(username="auditor-o9", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.AUDITOR)
        self.admin = Usuario.objects.create_user(username="admin-o9", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ADMINISTRADOR, is_staff=True)

    def _cenario(self):
        prestacao = self._prestacao("PROC-O9-SINT")
        outra = self._prestacao("PROC-O9-REAL", demonstracao=False)
        documento = Documento.objects.create(prestacao_contas=prestacao, nome_original="nota-o9.pdf", nome_armazenado="nota-o9.pdf", tipo_documento=TipoDocumento.NOTA_FISCAL, demonstracao=True)
        PaginaDocumento.objects.create(documento=documento, numero_pagina=1, metodo_extracao=MetodoExtracao.NATIVO, qualidade_extracao=QualidadeExtracao.SUFICIENTE, texto_extraido="Texto sintético.")
        Documento.objects.create(prestacao_contas=prestacao, nome_original="cego.pdf", nome_armazenado="cego.pdf", subtipo_documento=FONTE_EXCLUIDA_TESTE_CEGO, demonstracao=True)
        regra = RegraAnalise.objects.create(codigo="REG-O9", versao=1, categoria="Financeiro", titulo="Regra sintética", descricao_original="Texto original.", tipo_execucao=TipoExecucaoTecnica.DETERMINISTICA, capacidade=CapacidadeExecucao.AUTOMATICA, executor="sintetico")
        analise = ExecucaoAnalise.objects.create(prestacao_contas=prestacao, versao_catalogo="o9", sintese="NÃO CONCLUSIVO")
        ExecucaoRegra.objects.create(analise=analise, regra=regra, resultado_funcional="NÃO VERIFICÁVEL", status_tecnico=StatusTecnico.INCONCLUSIVO, snapshot={"codigo": "REG-O9"})
        ExecucaoRegra.objects.create(analise=analise, regra=regra, resultado_funcional="NÃO LOCALIZADO", status_tecnico=StatusTecnico.INCONCLUSIVO, snapshot={"codigo": "REG-O9"})
        evidencia = Evidencia.objects.create(codigo="EVD-O9", prestacao_contas=prestacao, tipo=TipoEvidencia.DOCUMENTAL, metodo_obtencao=MetodoObtencao.EXTRACAO, documento=documento, demonstracao=True)
        Evidencia.objects.create(codigo="EVD-O9-ORFA", prestacao_contas=prestacao, tipo=TipoEvidencia.ESTRUTURADA, metodo_obtencao=MetodoObtencao.MOTOR, demonstracao=True)
        achado = Achado.objects.create(codigo="ACH-O9", prestacao_contas=prestacao, analise=analise, titulo="Achado crítico sintético", descricao_factual="Fato.", categoria="Financeiro", natureza="financeiro", status=StatusAchado.EM_REVISAO, materialidade_financeira=Decimal("10.50"), criticidade=Criticidade.CRITICA, chave_consolidacao="o9-a", demonstracao=True)
        Achado.objects.create(codigo="ACH-O9-B", prestacao_contas=prestacao, analise=analise, titulo="Sem valor", descricao_factual="Fato.", status=StatusAchado.POTENCIAL, materialidade_financeira=None, criticidade=Criticidade.BAIXA, chave_consolidacao="o9-b", demonstracao=True)
        RevisaoAchado.objects.create(achado=achado, acao="confirmar", status_anterior="em_revisao", status_novo="confirmado", usuario=self.auditor)
        Norma.objects.create(tipo_norma=TipoNorma.LEI, numero="9", ano=2024, titulo="Norma vigente sintética", situacao=SituacaoNorma.VIGENTE, hash_sha256="a" * 64)
        modelo = ModeloInteligenciaArtificial.objects.create(provedor=ProvedorIA.SIMULADO, identificador_modelo="simulado-o9", nome_exibicao="Simulado O9")
        PrecoModeloInteligenciaArtificial.objects.create(modelo=modelo, vigencia_inicio=date(2024, 1, 1), vigencia_fim=date(2024, 6, 30), preco_entrada=Decimal("2"), preco_saida=Decimal("4"))
        PrecoModeloInteligenciaArtificial.objects.create(modelo=modelo, vigencia_inicio=date(2024, 7, 1), preco_entrada=Decimal("5"), preco_saida=Decimal("9"))
        UsoInteligenciaArtificial.objects.create(provedor=ProvedorIA.SIMULADO, modelo=modelo, identificador_modelo=modelo.identificador_modelo, agente="agente-o9", prestacao_contas=prestacao, iniciada_em=timezone.make_aware(datetime(2024, 3, 1, 12, 0)), status=StatusUso.SUCESSO, tokens_entrada=1000, tokens_saida=0, tokens_total=1000, chave_idempotencia="o9-preco-a", resposta_estruturada={"segredo": "sk-segredo-onda9"})
        UsoInteligenciaArtificial.objects.create(provedor=ProvedorIA.SIMULADO, modelo=modelo, identificador_modelo=modelo.identificador_modelo, agente="agente-o9", prestacao_contas=prestacao, iniciada_em=timezone.make_aware(datetime(2024, 8, 1, 12, 0)), status=StatusUso.ERRO_CONTROLADO, erro_normalizado="timeout", tokens_entrada=2000, tokens_saida=1000, tokens_total=3000, chave_idempotencia="o9-preco-b")
        UsoInteligenciaArtificial.objects.create(provedor=ProvedorIA.SIMULADO, agente="agente-sem-preco", prestacao_contas=prestacao, iniciada_em=timezone.now(), status=StatusUso.ERRO_CONTROLADO, tokens_entrada=0, tokens_saida=0, tokens_total=0, chave_idempotencia="o9-sem-telemetria")
        gt = GroundTruthPrestacao.objects.create(codigo="GT-O9", prestacao_contas=prestacao, modo=ModoGroundTruth.CEGO, status="congelado", hash_conteudo="b" * 64, dados_demonstracao=True)
        referencia = GroundTruthAchado.objects.create(codigo="GTA-O9", ground_truth=gt, titulo="FN crítico", materialidade=Decimal("80.00"), criticidade=CriticidadeReferencia.CRITICA)
        avaliacao = AvaliacaoInteligenciaArtificial.objects.create(codigo="AV-O9", prestacao_contas=prestacao, ground_truth=gt, status="concluida", metricas={"precisao": "0.5000", "recall": "0.5000"}, hash_conteudo="c" * 64, dados_demonstracao=True)
        CorrespondenciaAchado.objects.create(avaliacao=avaliacao, achado=achado, classificacao=ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO)
        CorrespondenciaAchado.objects.create(avaliacao=avaliacao, achado=achado, classificacao=ClassificacaoCorrespondencia.FALSO_POSITIVO)
        CorrespondenciaAchado.objects.create(avaliacao=avaliacao, ground_truth_achado=referencia, classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO)
        return {"prestacao": prestacao, "outra": outra, "achado": achado, "gt": gt, "avaliacao": avaliacao, "modelo": modelo, "evidencia": evidencia}

    def _prestacao(self, numero, demonstracao=True):
        from aplicacao.prestacoes_contas.models import PrestacaoContas

        return PrestacaoContas.objects.create(numero_processo=numero, demonstracao=demonstracao, data_inicio=date(2024, 1, 1), objeto="Sintético")

    def test_visao_com_dados_e_drill_down(self):
        cenario = self._cenario()
        self.client.force_login(self.consulta)
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertContains(resposta, "Visão 360°")
        self.assertContains(resposta, "Central de Atenção")
        self.assertContains(resposta, "Pipeline da análise")
        self.assertContains(resposta, cenario["achado"].titulo)
        self.assertContains(resposta, reverse("achados:detalhe", kwargs={"pk": cenario["achado"].pk}))

    def test_visao_sem_dados(self):
        self.client.force_login(self.consulta)
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertContains(resposta, "Sem prestações para os filtros selecionados.")
        self.assertContains(resposta, SEM_HISTORICO)
        self.assertContains(resposta, NAO_DISPONIVEL)
        self.assertNotContains(resposta, "NaN")

    def test_null_de_materialidade_nao_e_zero(self):
        prestacao = self._prestacao("PROC-O9-NULL")
        analise = ExecucaoAnalise.objects.create(prestacao_contas=prestacao, versao_catalogo="o9")
        Achado.objects.create(codigo="ACH-NULL", prestacao_contas=prestacao, analise=analise, titulo="Nulo", descricao_factual="Fato.", materialidade_financeira=None, chave_consolidacao="nulo", demonstracao=True)
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("painel:achados"))
        self.assertContains(resposta, NAO_DISPONIVEL)
        self.assertContains(resposta, "Sem materialidade")
        self.assertNotContains(resposta, ">0.00<")

    def test_serie_historica_insuficiente_e_suficiente(self):
        from aplicacao.painel.consultas.visao import montar_visao

        vazio = montar_visao(FiltrosPainel())
        self.assertIsNone(vazio.historico)
        self.assertEqual(vazio.mensagem_historico, SEM_HISTORICO)
        prestacao = self._prestacao("PROC-O9-MES")
        PrestacaoContas = prestacao.__class__
        PrestacaoContas.objects.filter(pk=prestacao.pk).update(criado_em=timezone.now() - timedelta(days=40))
        self._prestacao("PROC-O9-MES-2")
        cheio = montar_visao(FiltrosPainel())
        self.assertIsNotNone(cheio.historico)
        self.assertTrue(cheio.historico.tem_dados)

    def test_filtros_globais_e_combinacao(self):
        cenario = self._cenario()
        self.client.force_login(self.analista)
        pagina = self.client.get(reverse("painel:achados"), {"prestacao": cenario["prestacao"].pk, "criticidade": "critica"})
        self.assertContains(pagina, "Filtros ativos")
        self.assertContains(pagina, cenario["achado"].codigo)
        self.assertNotContains(pagina, "ACH-O9-B")
        self.assertContains(pagina, "Limpar filtros")

    def test_permissoes_e_urls_anteriores(self):
        self.client.force_login(self.consulta)
        for nome in ("painel:inicio", "painel:processos", "painel:documentos", "painel:normas", "painel:regras", "painel:evidencias", "painel:achados", "painel:pre_analise", "painel:revisao", "painel:ia_tecnico", "painel:operacao", "painel:finops", "ia:visao"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)
        self.assertEqual(self.client.get(reverse("painel:administracao")).status_code, 403)
        self.assertEqual(self.client.get(reverse("painel:saude")).status_code, 403)
        self.assertEqual(self.client.get(reverse("ia:laboratorio")).status_code, 403)
        for perfil in (self.analista, self.auditor):
            self.client.force_login(perfil)
            self.assertEqual(self.client.get(reverse("painel:inicio")).status_code, 200)
            self.assertEqual(self.client.get(reverse("painel:finops")).status_code, 200)
            self.assertEqual(self.client.get(reverse("ia:visao")).status_code, 200)
            self.assertEqual(self.client.get(reverse("painel:administracao")).status_code, 403)
            self.assertEqual(self.client.get(reverse("painel:saude")).status_code, 403)
            self.assertEqual(self.client.get(reverse("ia:laboratorio")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("painel:saude")).status_code, 200)
        self.assertContains(self.client.get(reverse("painel:administracao")), "não congela")
        self.assertEqual(self.client.get(reverse("ia:laboratorio")).status_code, 200)
        self.assertEqual(self.client.get(reverse("painel:viva")).status_code, 200)

    def test_documentos_normas_regras_evidencias(self):
        self._cenario()
        self.client.force_login(self.consulta)
        documentos = self.client.get(reverse("painel:documentos"))
        self.assertContains(documentos, "Nota fiscal")
        self.assertContains(documentos, "Nativo")
        self.assertContains(documentos, "Excluídos do teste cego")
        normas = self.client.get(reverse("painel:normas"))
        self.assertContains(normas, "Vigentes")
        self.assertContains(normas, "não fundamenta")
        regras = self.client.get(reverse("painel:regras"))
        self.assertContains(regras, "Não verificáveis")
        self.assertContains(regras, "Não localizadas")
        evidencias = self.client.get(reverse("painel:evidencias"))
        self.assertContains(evidencias, "Órfãs")
        self.assertContains(evidencias, "EVD-O9-ORFA")

    def test_pre_analise_revisao_e_ia_tecnico(self):
        from aplicacao.pareceres.models import PreAnaliseTecnica

        cenario = self._cenario()
        PreAnaliseTecnica.objects.create(codigo="PA-O9", prestacao_contas=cenario["prestacao"], execucao_analise=ExecucaoAnalise.objects.get(prestacao_contas=cenario["prestacao"]), versao=1, status="aguardando_revisao", titulo="Sintética", resumo_executivo="Síntese sem conclusão.", hash_conteudo="d" * 64, demonstracao=True, encaminhamento="submeter_ao_auditor")
        self.client.force_login(self.auditor)
        pre = self.client.get(reverse("painel:pre_analise"))
        self.assertContains(pre, "Aguardando revisão")
        self.assertNotContains(pre, "APROVADO")
        self.assertNotContains(pre, "REPROVADO")
        revisao = self.client.get(reverse("painel:revisao"))
        self.assertContains(revisao, "Tempo decorrido")
        self.assertContains(revisao, "Não é tempo de trabalho")
        ia = self.client.get(reverse("painel:ia_tecnico"))
        self.assertContains(ia, "Verdadeiros positivos")
        self.assertContains(ia, "Falsos negativos críticos")
        self.assertContains(ia, "80.00")
        self.assertNotContains(ia, "Nota da IA")

    def test_denominador_zero(self):
        from aplicacao.painel.consultas.abas import montar_ia_tecnico

        painel = montar_ia_tecnico(FiltrosPainel())
        precisao = next(item for item in painel.kpis if item.nome == "Precisão")
        self.assertEqual(precisao.exibicao, NAO_DISPONIVEL)

    def test_operacao_finops_e_segredo(self):
        cenario = self._cenario()
        self.client.force_login(self.consulta)
        operacao = self.client.get(reverse("painel:operacao"))
        self.assertContains(operacao, "agente-o9")
        self.assertContains(operacao, "timeout")
        self.assertNotContains(operacao, "sk-segredo-onda9")
        self.assertNotContains(operacao, "Authorization")
        finops = self.client.get(reverse("painel:finops"))
        self.assertContains(finops, "Custo total")
        self.assertNotContains(finops, "sk-segredo-onda9")
        resumo = montar_finops(FiltrosPainel(prestacao=cenario["prestacao"].pk))
        custo = next(item for item in resumo.kpis if item.nome == "Custo total")
        self.assertNotEqual(custo.exibicao, "0.000000")
        self.assertIn(".", custo.exibicao)
        sem_preco = next(item for item in resumo.kpis if item.nome == "Chamadas sem preço vigente")
        self.assertEqual(sem_preco.exibicao, "1")

    def test_troca_de_preco_por_vigencia(self):
        cenario = self._cenario()
        usos = list(UsoInteligenciaArtificial.objects.filter(modelo=cenario["modelo"]).order_by("iniciada_em"))
        from aplicacao.painel.consultas.finops import _precos

        mapa = _precos({cenario["modelo"].pk})
        primeiro = custo_da_chamada(usos[0], mapa)
        segundo = custo_da_chamada(usos[1], mapa)
        self.assertEqual(primeiro, Decimal("0.002000"))
        self.assertEqual(segundo, Decimal("0.019000"))
        self.assertNotEqual(primeiro, segundo)

    def test_isolamento_ground_truth_e_congelados(self):
        cenario = self._cenario()
        hash_gt = cenario["gt"].hash_conteudo
        hash_av = cenario["avaliacao"].hash_conteudo
        self.client.force_login(self.admin)
        self.client.get(reverse("painel:inicio"))
        self.client.get(reverse("painel:ia_tecnico"))
        cenario["gt"].refresh_from_db()
        cenario["avaliacao"].refresh_from_db()
        self.assertEqual(cenario["gt"].hash_conteudo, hash_gt)
        self.assertEqual(cenario["avaliacao"].hash_conteudo, hash_av)
        raiz = Path(__file__).resolve().parent / "consultas"
        for arquivo in raiz.glob("*.py"):
            texto = arquivo.read_text(encoding="utf-8")
            self.assertNotIn("criar_avaliacao", texto)
            self.assertNotIn("definir_regra", texto)
            self.assertNotIn("sk-", texto)

    def test_demonstracao_identificada_e_filtrada(self):
        cenario = self._cenario()
        self.client.force_login(self.consulta)
        tudo = self.client.get(reverse("painel:processos"))
        self.assertContains(tudo, "demonstração")
        self.assertContains(tudo, cenario["prestacao"].numero_processo)
        operacional = self.client.get(reverse("painel:processos"), {"origem": "operacional"})
        self.assertContains(operacional, cenario["outra"].numero_processo)
        self.assertNotContains(operacional, cenario["prestacao"].numero_processo)

    def test_layout_visual_sem_exportacao_e_sem_faixa(self):
        self._cenario()
        self.client.force_login(self.consulta)
        pagina = self.client.get(reverse("painel:inicio"))
        self.assertContains(pagina, "Aplicar filtros")
        self.assertContains(pagina, "Central de Atenção")
        self.assertContains(pagina, "Pipeline da análise")
        self.assertContains(pagina, "não é taxa de conversão")
        self.assertContains(pagina, "30d")
        self.assertContains(pagina, "Nenhum indicador aprova ou reprova a prestação.")
        self.assertNotContains(pagina, "O recorte inclui")
        self.assertNotContains(pagina, "Exportar")
        self.assertEqual(pagina.content.decode().count('href="/finops/"'), 1)
        processos = self.client.get(reverse("painel:processos"))
        self.assertContains(processos, "Aplicar filtros")
        self.assertContains(processos, "Filtros")

    def test_sem_cdn_e_menu_responsivo(self):
        css = Path(__file__).resolve().parents[1].joinpath("static/css/cge.css").read_text(encoding="utf-8")
        central = Path(__file__).resolve().parents[1].joinpath("templates/painel/central.html").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 991px)", css)
        self.assertIn("overflow: auto", css)
        bloco_mobile = css.split("@media (max-width: 991px)", 1)[1].split(".abas-painel", 1)[0]
        self.assertIn("min(18rem, 88vw)", bloco_mobile)
        self.assertNotIn("width: 100%", bloco_mobile)
        self.assertNotIn("cdn.", central)
        self.assertNotIn("jsdelivr", central)
        self.assertIn("abas-painel", central)
        self.assertIn("table-responsive", Path(__file__).resolve().parents[1].joinpath("templates/painel/_tabela.html").read_text(encoding="utf-8"))
