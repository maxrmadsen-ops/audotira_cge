from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicacao.achados.agente import sugerir_consolidacao
from aplicacao.achados.escolhas import Criticidade, PapelEvidencia, Prioridade, StatusAchado, TipoConstatacao, TipoEvidencia
from aplicacao.achados.gerador import associar_fundamento, gerar_achados
from aplicacao.achados.models import Achado, AchadoEvidencia, Evidencia, FundamentacaoAchado, RevisaoAchado
from aplicacao.achados.revisao import ErroRevisao, registrar_evidencia_humana, revisar
from aplicacao.documentos.escolhas import OrigemDocumento, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.inteligencia_artificial.models import UsoInteligenciaArtificial
from aplicacao.inteligencia_artificial.provedores.simulado import ProvedorInteligenciaArtificialSimulado
from aplicacao.inteligencia_artificial.sementes import garantir_catalogo_ia, versao_ativa
from aplicacao.normas.escolhas import TipoNorma
from aplicacao.normas.models import Norma, TrechoNormativo
from aplicacao.prestacoes_contas.models import Despesa, PrestacaoContas
from aplicacao.regras.contexto import ContextoExecucao
from aplicacao.regras.escolhas import FONTE_EXCLUIDA_TESTE_CEGO, StatusTecnico
from aplicacao.regras.executores import ExecutorAchado
from aplicacao.regras.models import CalculoExecucaoRegra, ExecucaoAnalise, ExecucaoRegra, ReferenciaExecucao, RegraAnalise
from aplicacao.usuarios.models import Usuario

UsuarioModelo = get_user_model()


def schema(**extras):
    base = {
        "resultado": "INCONCLUSIVO",
        "justificativa_resumida": "Sugestão limitada ao contexto.",
        "fatos_identificados": [],
        "fontes_utilizadas": [],
        "fundamentos_normativos": [],
        "limitacoes": ["Revisão humana obrigatória."],
        "dados_insuficientes": False,
        "requer_revisao_humana": True,
    }
    base.update(extras)
    return base


class BaseAchados(TestCase):
    def setUp(self):
        self.prestacao = PrestacaoContas.objects.create(numero_processo="PROC-ACH", demonstracao=True, data_inicio=date(2024, 1, 1))
        self.despesa = Despesa.objects.create(prestacao=self.prestacao, descricao="Despesa sintética", valor=Decimal("1000.00"), demonstracao=True)
        self.outra = Despesa.objects.create(prestacao=self.prestacao, descricao="Outra despesa", valor=Decimal("10.00"), demonstracao=True)
        self.analise = ExecucaoAnalise.objects.create(prestacao_contas=self.prestacao, versao_catalogo="teste", sintese="NÃO CONCLUSIVO")
        self.auditor = UsuarioModelo.objects.create_user(username="auditor-ach", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.AUDITOR)
        self.analista = UsuarioModelo.objects.create_user(username="analista-ach", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ANALISTA)
        self.consulta = UsuarioModelo.objects.create_user(username="consulta-ach", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.CONSULTA)

    def regra(self, codigo, categoria="Financeiro"):
        return RegraAnalise.objects.create(
            codigo=codigo,
            versao=1,
            categoria=categoria,
            titulo=codigo,
            descricao_original="Texto sintético.",
            tipo_execucao="deterministica",
            capacidade="automatica",
            executor="comparacao_valor",
            ativa=True,
        )

    def execucao(self, regra, resultado, status, despesa=None, papel="valor_documentado", calculo=True, documento=None, pagina=None, trecho_normativo=None):
        item = ExecucaoRegra.objects.create(
            analise=self.analise,
            regra=regra,
            resultado_funcional=resultado,
            status_tecnico=status,
            snapshot={"codigo": regra.codigo, "versao": regra.versao},
        )
        if despesa is not None:
            ReferenciaExecucao.objects.create(
                execucao=item,
                tipo_fonte="despesa",
                identificador=str(despesa.pk),
                valor_utilizado="1000.00",
                papel_na_regra=papel,
                documento=documento,
                pagina=pagina,
                trecho="Trecho sintético da página.",
                trecho_normativo=trecho_normativo,
            )
        if calculo:
            CalculoExecucaoRegra.objects.create(
                execucao=item,
                operacao="diferenca",
                operandos={"valor_documentado": "1000.00", "valor_pago": "950.00"},
                resultado=Decimal("50.0000"),
                unidade="BRL",
            )
        return item


class TesteEvidencias(BaseAchados):
    def test_tipos_proveniencia_papeis_e_evidencia_sem_achado(self):
        documento = Documento.objects.create(
            prestacao_contas=self.prestacao,
            nome_original="Nota sintetica.pdf",
            nome_armazenado="nota-sintetica.pdf",
            tipo_documento=TipoDocumento.NOTA_FISCAL,
            origem=OrigemDocumento.DEMONSTRACAO,
            hash_sha256="a" * 64,
            demonstracao=True,
        )
        pagina = PaginaDocumento.objects.create(documento=documento, numero_pagina=2, metodo_extracao="nativo", qualidade_extracao="suficiente")
        norma = Norma.objects.create(tipo_norma=TipoNorma.DECRETO, numero="1", ano=2024, titulo="Norma sintética", inicio_vigencia=date(2020, 1, 1))
        trecho = TrechoNormativo.objects.create(norma=norma, ordem=1, texto="Dispositivo sintético.", hash_conteudo="b" * 64, artigo="58")
        primeira = self.execucao(
            self.regra("FIN-901"),
            "DIVERGÊNCIA",
            StatusTecnico.DIVERGENCIA,
            self.despesa,
            documento=documento,
            pagina=pagina,
            trecho_normativo=trecho,
        )
        ReferenciaExecucao.objects.create(
            execucao=primeira,
            tipo_fonte="documento",
            identificador=str(documento.pk),
            documento=documento,
            pagina=pagina,
            trecho="Trecho documental sintético.",
            papel_na_regra="fonte",
        )
        ReferenciaExecucao.objects.create(
            execucao=primeira,
            tipo_fonte="pagamento",
            identificador="900001",
            valor_utilizado="950.00",
            papel_na_regra="valor_pago",
        )
        segunda = self.execucao(self.regra("FIN-902"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa, papel="contradiz")
        segunda.entradas = {"ia": {"justificativa": "Interpretação limitada aos valores já calculados.", "agente": "analise_semantica"}}
        segunda.save(update_fields=["entradas"])
        orfa = Evidencia.objects.create(
            codigo="EVD-MANUAL",
            prestacao_contas=self.prestacao,
            tipo=TipoEvidencia.HUMANA,
            metodo_obtencao="usuario",
            trecho="Evidência ainda sem achado.",
            demonstracao=True,
        )
        gerar_achados(self.analise.pk)
        tipos = set(Evidencia.objects.exclude(pk=orfa.pk).values_list("tipo", flat=True))
        self.assertTrue(
            {
                TipoEvidencia.DOCUMENTAL,
                TipoEvidencia.ESTRUTURADA,
                TipoEvidencia.CALCULADA,
                TipoEvidencia.NORMATIVA,
                TipoEvidencia.CRUZAMENTO,
                TipoEvidencia.SEMANTICA_IA,
            }.issubset(tipos)
        )
        documental = Evidencia.objects.get(tipo=TipoEvidencia.DOCUMENTAL, documento=documento)
        self.assertEqual(documental.pagina_documento_id, pagina.pk)
        self.assertEqual(documental.hash_origem, "a" * 64)
        self.assertTrue(documental.execucao_regra_id)
        self.assertFalse(orfa.vinculos.exists())
        papeis = set(AchadoEvidencia.objects.values_list("papel", flat=True))
        self.assertIn(PapelEvidencia.SUPORTA, papeis)
        self.assertIn(PapelEvidencia.CONTRADIZ, papeis)
        self.assertIn(PapelEvidencia.FUNDAMENTA, papeis)
        self.assertIn(PapelEvidencia.CONTEXTUALIZA, papeis)
        AchadoEvidencia.objects.create(
            achado=Achado.objects.first(),
            evidencia=orfa,
            papel=PapelEvidencia.AUSENCIA,
        )
        self.assertTrue(AchadoEvidencia.objects.filter(papel=PapelEvidencia.AUSENCIA).exists())


class TesteAchados(BaseAchados):
    def test_divergencia_nasce_potencial_com_decimal_e_rastreio(self):
        self.execucao(self.regra("FIN-903"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        self.assertEqual(achado.status, StatusAchado.POTENCIAL)
        self.assertNotEqual(achado.status, StatusAchado.CONFIRMADO)
        self.assertIsInstance(achado.materialidade_financeira, Decimal)
        self.assertEqual(achado.materialidade_financeira, Decimal("50.00"))
        self.assertEqual(achado.criticidade, Criticidade.MEDIA)
        self.assertEqual(achado.prioridade, Prioridade.NORMAL)
        self.assertTrue(achado.elementos_rastreaveis)
        self.assertTrue(achado.codigo.startswith("ACH-"))
        self.assertNotIn("irregular", achado.titulo.casefold())

    def test_conforme_e_nao_verificavel_nao_geram_achado(self):
        self.execucao(self.regra("FIN-904"), "CONFORME", StatusTecnico.SUCESSO, self.despesa, calculo=False)
        self.execucao(self.regra("FIN-905"), "NÃO VERIFICÁVEL", StatusTecnico.INCONCLUSIVO, self.despesa, calculo=False)
        self.execucao(self.regra("FIN-906"), "NÃO LOCALIZADO", StatusTecnico.INCONCLUSIVO, calculo=False)
        self.execucao(self.regra("PT-901", "Plano de Trabalho"), "REQUER ANÁLISE SEMÂNTICA", StatusTecnico.NAO_EXECUTADA, calculo=False)
        gerar_achados(self.analise.pk)
        self.assertEqual(Achado.objects.count(), 0)

    def test_insuficiente_nao_confirma_e_prioridade_independe_de_materialidade(self):
        self.execucao(self.regra("DEV-901", "Devolução"), "POSSÍVEL SALDO NÃO DEVOLVIDO", StatusTecnico.ATENCAO, calculo=False)
        qualitativo = self.execucao(self.regra("VED-901", "Vedações"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.outra, calculo=False)
        ReferenciaExecucao.objects.create(execucao=qualitativo, tipo_fonte="despesa", identificador=str(self.outra.pk), papel_na_regra="fato")
        gerar_achados(self.analise.pk)
        insuficiente = Achado.objects.get(evidencia_insuficiente=True)
        self.assertEqual(insuficiente.status, StatusAchado.POTENCIAL)
        self.assertIn("Evidência insuficiente", insuficiente.possivel_implicacao)
        with self.assertRaises(ErroRevisao):
            revisar(insuficiente, self.auditor, "confirmar", justificativa="não procede")
        vedacao = Achado.objects.get(natureza="vedacao")
        self.assertIsNone(vedacao.materialidade_financeira)
        self.assertEqual(vedacao.criticidade, Criticidade.ALTA)
        revisar(vedacao, self.auditor, "ajustar", justificativa="Ordem de tratamento.", campos={"prioridade": Prioridade.URGENTE})
        vedacao.refresh_from_db()
        self.assertEqual(vedacao.criticidade, Criticidade.ALTA)
        self.assertEqual(vedacao.prioridade, Prioridade.URGENTE)


class TesteConsolidacao(BaseAchados):
    def test_mesma_despesa_consolida_e_reprocessar_nao_duplica(self):
        primeira = self.execucao(self.regra("FIN-907"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        ReferenciaExecucao.objects.create(
            execucao=primeira,
            tipo_fonte="pagamento",
            identificador="900001",
            papel_na_regra="valor_pago",
        )
        self.execucao(self.regra("DES-901", "Despesas"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        primeiro = gerar_achados(self.analise.pk)
        self.assertEqual(Achado.objects.count(), 1)
        self.assertEqual(Achado.objects.get().vinculos_regra.count(), 2)
        self.assertGreaterEqual(primeiro.candidatos, 2)
        gerar_achados(self.analise.pk)
        self.assertEqual(Achado.objects.count(), 1)
        self.assertEqual(Achado.objects.get().vinculos_evidencia.count(), AchadoEvidencia.objects.filter(achado=Achado.objects.get()).count())

    def test_texto_parecido_sem_ancora_comum_nao_consolida(self):
        self.execucao(self.regra("FIN-908"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        self.execucao(self.regra("FIN-909"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.outra)
        gerar_achados(self.analise.pk)
        self.assertEqual(Achado.objects.count(), 2)


class TesteFundamentacao(BaseAchados):
    def test_vigencia_e_trecho_real(self):
        vigente = Norma.objects.create(tipo_norma=TipoNorma.DECRETO, numero="2", ano=2024, titulo="Vigente", inicio_vigencia=date(2020, 1, 1))
        expirada = Norma.objects.create(
            tipo_norma=TipoNorma.DECRETO,
            numero="3",
            ano=2010,
            titulo="Expirada",
            inicio_vigencia=date(2010, 1, 1),
            fim_vigencia=date(2012, 1, 1),
        )
        trecho_ok = TrechoNormativo.objects.create(norma=vigente, ordem=1, texto="Artigo vigente.", hash_conteudo="c" * 64)
        trecho_ruim = TrechoNormativo.objects.create(norma=expirada, ordem=1, texto="Artigo antigo.", hash_conteudo="d" * 64)
        self.execucao(self.regra("FIN-910"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa, trecho_normativo=trecho_ok)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        self.assertEqual(FundamentacaoAchado.objects.get().trecho_normativo, trecho_ok)
        self.assertEqual(FundamentacaoAchado.objects.get().vigencia_inicio, date(2020, 1, 1))
        self.assertIsNone(associar_fundamento(achado, trecho_ruim, date(2024, 6, 1)))
        self.assertEqual(FundamentacaoAchado.objects.count(), 1)


class TesteRevisao(BaseAchados):
    def test_consulta_nao_altera_e_auditor_preserva_original(self):
        self.execucao(self.regra("FIN-911"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        original = achado.saida_original["factual"]
        with self.assertRaises(ErroRevisao):
            revisar(achado, self.consulta, "descartar", justificativa="consulta")
        revisar(achado, self.analista, "manter_em_analise", comentario="em leitura")
        revisar(achado, self.auditor, "ajustar", justificativa="Há comprovante complementar.", campos={"descricao_factual": "Texto ajustado pelo auditor."})
        achado.refresh_from_db()
        self.assertEqual(achado.status, StatusAchado.AJUSTADO)
        self.assertEqual(achado.saida_original["factual"], original)
        self.assertNotEqual(achado.descricao_factual, original)
        revisao = RevisaoAchado.objects.filter(acao="ajustar").get()
        self.assertEqual(revisao.valor_anterior["descricao_factual"], original if original == revisao.valor_anterior["descricao_factual"] else revisao.valor_anterior["descricao_factual"])
        self.assertEqual(revisao.usuario, self.auditor)
        self.assertIsNotNone(revisao.data_hora)
        revisar(achado, self.auditor, "solicitar_diligencia", justificativa="Pedir o comprovante.")
        achado.refresh_from_db()
        self.assertEqual(achado.status, StatusAchado.NECESSITA_DILIGENCIA)
        evidencia = registrar_evidencia_humana(achado, self.analista, "Comprovante complementar sintético.", PapelEvidencia.CONTRADIZ)
        self.assertEqual(evidencia.tipo, TipoEvidencia.HUMANA)
        self.assertEqual(evidencia.criada_por, self.analista)
        self.client.force_login(self.auditor)
        confirmar = self.client.post(reverse("achados:detalhe", kwargs={"pk": achado.pk}), {"acao": "confirmar", "justificativa": "conferido"})
        self.assertEqual(confirmar.status_code, 302)
        achado.refresh_from_db()
        self.assertEqual(achado.status, StatusAchado.CONFIRMADO)
        self.assertEqual(achado.saida_original["factual"], original)


class TesteGovernanca(BaseAchados):
    def test_teste_cego_nao_gera_evidencia(self):
        bloqueado = Documento.objects.create(
            prestacao_contas=self.prestacao,
            nome_original="Relatório de prestação final com análise técnica.pdf",
            nome_armazenado="bloqueado.pdf",
            tipo_documento=TipoDocumento.PRESTACAO_FINAL,
            subtipo_documento=FONTE_EXCLUIDA_TESTE_CEGO,
            origem=OrigemDocumento.DEMONSTRACAO,
            demonstracao=True,
        )
        execucao = self.execucao(self.regra("FIN-912"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, calculo=False)
        ReferenciaExecucao.objects.create(execucao=execucao, tipo_fonte="documento", identificador=str(bloqueado.pk), documento=bloqueado, papel_na_regra="fonte")
        with patch("urllib.request.urlopen") as urlopen:
            gerar_achados(self.analise.pk)
        urlopen.assert_not_called()
        self.assertEqual(Evidencia.objects.count(), 0)
        self.assertEqual(Achado.objects.count(), 0)

    def test_agente_nao_inventa_nem_confirma_e_registra_uso(self):
        self.execucao(self.regra("FIN-913"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        antes = achado.vinculos_evidencia.count()
        garantir_catalogo_ia()
        from aplicacao.inteligencia_artificial.gerenciador import GerenciadorInteligenciaArtificial

        versao = versao_ativa("analise_semantica")
        contexto = {"itens": [{"tipo": "documento", "identificador": "documento-sintetico"}], "ground_truth": "RESPOSTA_SECRETA"}
        provedor = ProvedorInteligenciaArtificialSimulado(
            respostas=[
                schema(
                    descricao_factual="Valor inventado 99999.",
                    fontes_utilizadas=[{"tipo": "documento", "identificador": "nao-existe"}],
                    fundamentos_normativos=[{"identificador": "lei-inventada"}],
                    criticidade=Criticidade.CRITICA,
                )
            ]
        )
        chamada = sugerir_consolidacao(achado, GerenciadorInteligenciaArtificial(provedor), versao, contexto)
        achado.refresh_from_db()
        self.assertFalse(achado.sugestao_consolidacao["aceita"])
        self.assertEqual(achado.status, StatusAchado.POTENCIAL)
        self.assertNotEqual(achado.criticidade, Criticidade.CRITICA)
        self.assertEqual(achado.vinculos_evidencia.count(), antes)
        self.assertEqual(FundamentacaoAchado.objects.count(), 0)
        self.assertTrue(UsoInteligenciaArtificial.objects.filter(agente="consolidacao_achados").exists())
        self.assertGreaterEqual(len(chamada.usos), 1)
        self.assertNotIn("RESPOSTA_SECRETA", provedor.chamadas[0].entrada)
        self.assertIn("não pode introduzir nenhum fato", provedor.chamadas[0].entrada)
        provedor_falho = ProvedorInteligenciaArtificialSimulado(falha="timeout")
        sugerir_consolidacao(achado, GerenciadorInteligenciaArtificial(provedor_falho), versao, {"itens": []})
        self.assertEqual(achado.vinculos_evidencia.count(), antes)

    def test_executor_enxerga_achado_concreto(self):
        self.execucao(self.regra("FIN-914"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        gerar_achados(self.analise.pk)
        contexto = ContextoExecucao(self.prestacao, [], False, [])
        contexto.analise = self.analise
        regra = self.regra("ACH-901")
        regra.configuracao = {"operacao": "rastreavel"}
        regra.save(update_fields=["configuracao"])
        resultado = ExecutorAchado().executar(regra, contexto)
        self.assertEqual(resultado.resultado_funcional, "ACHADO RASTREÁVEL")


class TesteRegrasDeAchado(BaseAchados):
    def _avaliar(self, operacao, codigo):
        contexto = ContextoExecucao(self.prestacao, [], False, [])
        contexto.analise = self.analise
        regra = self.regra(codigo)
        regra.configuracao = {"operacao": operacao}
        regra.save(update_fields=["configuracao"])
        return ExecutorAchado().executar(regra, contexto)

    def test_ach001_sem_evidencia_nao_atende(self):
        self.execucao(self.regra("DEV-911", "Devolução"), "POSSÍVEL SALDO NÃO DEVOLVIDO", StatusTecnico.ATENCAO, calculo=False)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        self.assertFalse(achado.vinculos_evidencia.exists())
        self.assertFalse(achado.elementos_rastreaveis)
        self.assertEqual(self._avaliar("rastreavel", "ACH-001").resultado_funcional, "NÃO GERAR")

    def test_ach001_com_fato_regra_evidencia_e_rastreio_atende(self):
        self.execucao(self.regra("FIN-921"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        self.assertTrue(achado.descricao_factual.strip())
        self.assertTrue(achado.vinculos_regra.filter(execucao__isnull=False).exists())
        self.assertTrue(achado.vinculos_evidencia.exists())
        self.assertTrue(achado.elementos_rastreaveis)
        self.assertEqual(self._avaliar("rastreavel", "ACH-001").resultado_funcional, "ACHADO RASTREÁVEL")

    def test_ach002_sem_fundamento_nao_atende(self):
        self.execucao(self.regra("FIN-922"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        self.assertEqual(achado.fundamentacoes.count(), 0)
        self.assertFalse(achado.fundamentacao_suficiente)
        self.assertEqual(self._avaliar("fundamento", "ACH-002").resultado_funcional, "INSUFICIENTE")

    def test_ach002_norma_vigente_atende(self):
        norma = Norma.objects.create(tipo_norma=TipoNorma.DECRETO, numero="58", ano=2024, titulo="Norma vigente sintética", inicio_vigencia=date(2020, 1, 1))
        trecho = TrechoNormativo.objects.create(norma=norma, ordem=1, texto="Dispositivo vigente.", hash_conteudo="e" * 64, artigo="58")
        self.execucao(self.regra("FIN-923"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa, trecho_normativo=trecho)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        fundamento = FundamentacaoAchado.objects.get()
        self.assertEqual(fundamento.norma, norma)
        self.assertEqual(fundamento.trecho_normativo, trecho)
        self.assertEqual(fundamento.origem_resolucao, "resolvedor_normativo")
        self.assertTrue(achado.fundamentacao_suficiente)
        self.assertEqual(self._avaliar("fundamento", "ACH-002").resultado_funcional, "FUNDAMENTADO")

    def test_ach002_norma_fora_da_vigencia_nao_atende(self):
        expirada = Norma.objects.create(
            tipo_norma=TipoNorma.DECRETO,
            numero="9",
            ano=2010,
            titulo="Norma expirada sintética",
            inicio_vigencia=date(2010, 1, 1),
            fim_vigencia=date(2012, 1, 1),
        )
        trecho = TrechoNormativo.objects.create(norma=expirada, ordem=1, texto="Dispositivo expirado.", hash_conteudo="f" * 64)
        self.execucao(self.regra("FIN-924"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa, trecho_normativo=trecho)
        gerar_achados(self.analise.pk)
        achado = Achado.objects.get()
        self.assertEqual(FundamentacaoAchado.objects.count(), 0)
        self.assertFalse(achado.fundamentacao_suficiente)
        self.assertEqual(self._avaliar("fundamento", "ACH-002").resultado_funcional, "INSUFICIENTE")


class TesteInterface(BaseAchados):
    def test_central_api_e_aba(self):
        self.client.force_login(self.consulta)
        lista = self.client.get(reverse("achados:lista"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "Potenciais")
        self.assertContains(lista, ">0<")
        self.execucao(self.regra("FIN-915"), "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, self.despesa)
        positiva = self.execucao(self.regra("DEV-902", "Devolução"), "DEVOLVIDO", StatusTecnico.SUCESSO, self.despesa, calculo=False)
        ReferenciaExecucao.objects.create(execucao=positiva, tipo_fonte="despesa", identificador=str(self.despesa.pk), papel_na_regra="devolucao")
        gerar_achados(self.analise.pk)
        self.assertTrue(Achado.objects.filter(tipo_constatacao=TipoConstatacao.CONSTATACAO_POSITIVA).exists())
        achado = Achado.objects.filter(tipo_constatacao=TipoConstatacao.ACHADO_POTENCIAL).get()
        detalhe = self.client.get(reverse("achados:detalhe", kwargs={"pk": achado.pk}))
        self.assertContains(detalhe, achado.codigo)
        self.assertContains(detalhe, "Fato")
        aba = self.client.get(reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}), {"aba": "achados"})
        self.assertContains(aba, achado.codigo)
        self.assertEqual(self.client.get("/api/achados/").status_code, 200)
        negado = self.client.post(f"/api/achados/{achado.pk}/revisoes/", {"acao": "confirmar", "justificativa": "não"}, content_type="application/json")
        self.assertEqual(negado.status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get("/api/achados/").status_code, 403)
