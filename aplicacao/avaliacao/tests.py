import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from aplicacao.achados.escolhas import MetodoObtencao, PapelEvidencia, TipoEvidencia
from aplicacao.achados.models import Achado, AchadoEvidencia, AchadoRegra, Evidencia
from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.avaliacao.comparacao import token
from aplicacao.avaliacao.comparador import registrar_sugestao_semantica
from aplicacao.avaliacao.escolhas import ClassificacaoCorrespondencia, CriticidadeReferencia, ModoGroundTruth
from aplicacao.avaliacao.excecoes import ErroAvaliacao
from aplicacao.avaliacao.executar import congelar_avaliacao, criar_avaliacao, executar_comparacao, nova_versao_avaliacao
from aplicacao.avaliacao.ground_truth import (
    adicionar_achado,
    congelar,
    criar_ground_truth,
    definir_regra,
    enviar_validacao,
    nova_versao,
    validar,
)
from aplicacao.avaliacao.hash_conteudo import calcular_hash_avaliacao, calcular_hash_ground_truth
from aplicacao.avaliacao.metricas import calcular_classificacao, materialidade_falsos_negativos
from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial, GroundTruthPrestacao
from aplicacao.avaliacao.revisao import revisar_correspondencia
from aplicacao.avaliacao.tarefas import executar_avaliacao_task
from aplicacao.documentos.models import Documento
from aplicacao.inteligencia_artificial.preparacao import preparar_contexto
from aplicacao.normas.escolhas import SituacaoNorma, TipoNorma
from aplicacao.normas.models import Norma, TrechoNormativo
from aplicacao.pareceres.contexto import montar_contexto
from aplicacao.pareceres.escolhas import OrigemConteudo, StatusPreAnalise, StatusValidacaoAfirmacao, TipoAfirmacao, TipoSecao
from aplicacao.pareceres.models import AfirmacaoPreAnalise, PreAnaliseTecnica, SecaoPreAnalise
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.regras.escolhas import CapacidadeExecucao, StatusTecnico, TipoExecucaoTecnica
from aplicacao.regras.models import ExecucaoAnalise, ExecucaoRegra, RegraAnalise
from aplicacao.usuarios.models import Usuario

FRASE = "GT-SEGREDO-ONDA8-XYZ"
SEGREDO_IA = "ACHADO-IA-SECRETO-CEGO"


class TesteMetricasPuras(SimpleTestCase):
    def test_precisao_recall_e_f1_explicitos(self):
        resultado = calcular_classificacao(tp=8, fp=2, fn=1)
        self.assertEqual(resultado["precisao"], Decimal("0.8000"))
        recall = (Decimal(8) / Decimal(9)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        self.assertEqual(resultado["recall"], recall)
        f1 = (2 * resultado["precisao"] * resultado["recall"] / (resultado["precisao"] + resultado["recall"])).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        self.assertEqual(resultado["f1"], f1)
        self.assertIsInstance(resultado["precisao"], Decimal)

    def test_divisao_por_zero_nao_inventa_zero(self):
        resultado = calcular_classificacao(tp=0, fp=0, fn=0)
        self.assertIsNone(resultado["precisao"])
        self.assertIsNone(resultado["recall"])
        self.assertIsNone(resultado["f1"])

    def test_nao_aplicavel_permanece_distinto(self):
        self.assertNotEqual(token("NÃO APLICÁVEL"), token("NÃO VERIFICÁVEL"))
        self.assertEqual(token("NÃO LOCALIZADO"), "nao_localizado")
        self.assertNotEqual(token("NÃO LOCALIZADO"), token("NÃO VERIFICÁVEL"))


class BaseAvaliacao(TestCase):
    def setUp(self):
        UsuarioModelo = get_user_model()
        self.auditor = UsuarioModelo.objects.create_user(username="auditor-av", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.AUDITOR)
        self.analista = UsuarioModelo.objects.create_user(username="analista-av", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ANALISTA)
        self.consulta = UsuarioModelo.objects.create_user(username="consulta-av", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.CONSULTA)
        self.admin = UsuarioModelo.objects.create_user(username="admin-av", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ADMINISTRADOR)
        self.prestacao = PrestacaoContas.objects.create(numero_processo="PROC-AV-SINT", demonstracao=True, data_inicio=date(2024, 1, 1), objeto="Objeto sintético")
        self.analise = ExecucaoAnalise.objects.create(prestacao_contas=self.prestacao, versao_catalogo="sintetica", sintese="NÃO CONCLUSIVO")
        self.norma = Norma.objects.create(tipo_norma=TipoNorma.LEI, numero="8", ano=2024, titulo="Norma sintética vigente", situacao=SituacaoNorma.VIGENTE, hash_sha256="a" * 64)
        self.trecho = TrechoNormativo.objects.create(norma=self.norma, ordem=1, texto="Dispositivo sintético vigente.", hash_conteudo="b" * 64, artigo="1")
        self.norma_revogada = Norma.objects.create(tipo_norma=TipoNorma.LEI, numero="9", ano=2020, titulo="Norma sintética revogada", situacao=SituacaoNorma.REVOGADA, hash_sha256="c" * 64)
        self.documento = Documento.objects.create(prestacao_contas=self.prestacao, nome_original="Nota sintetica avaliacao.pdf", nome_armazenado="nota-av.pdf", demonstracao=True)
        self.regra_tp = self._regra("REG-TP", "Financeiro")
        self.regra_div = self._regra("REG-DIV", "Despesas")
        self.regra_nv = self._regra("REG-NV", "Prazo")
        self.regra_nl = self._regra("REG-NL", "Documentação")
        self.regra_na = self._regra("REG-NA", "Contexto")
        self.regra_sg = self._regra("REG-SG", "Pagamentos")
        self.regra_fe = self._regra("REG-FE", "Governança da IA", tipo=TipoExecucaoTecnica.FORA_ESCOPO_V1, capacidade=CapacidadeExecucao.FORA_ESCOPO)
        self.regra_amb = self._regra("REG-AMB", "Financeiro")
        self.regra_misto = self._regra("REG-MIX", "Nota fiscal")
        self.ev1 = self._evidencia("EVD-AV-1")
        self.ev2 = self._evidencia("EVD-AV-2")
        self.ev3 = self._evidencia("EVD-AV-3")
        self.exec_tp = self._execucao(self.regra_tp, "DIVERGÊNCIA", "limitação sintética de prazo")
        self.exec_div = self._execucao(self.regra_div, "CONFORME")
        self.exec_nv = self._execucao(self.regra_nv, "NÃO VERIFICÁVEL")
        self.exec_nl = self._execucao(self.regra_nl, "NÃO LOCALIZADO")
        self.exec_na = self._execucao(self.regra_na, "NÃO APLICÁVEL")
        self.exec_sg = self._execucao(self.regra_sg, "CONFORME")
        self.exec_fe = self._execucao(self.regra_fe, "NÃO REALIZADA – ESCOPO DA V1")
        self.exec_amb = self._execucao(self.regra_amb, "DIVERGÊNCIA")
        self.exec_mix = self._execucao(self.regra_misto, "NÃO APLICÁVEL")
        self.achado_tp = self._achado("ACH-AV-TP", "Texto completamente diferente da referência", "Financeiro", Decimal("50.00"), self.regra_tp, self.ev1, self.exec_tp)
        self.achado_fp = self._achado("ACH-AV-FP", "Achado somente da solução", "Bancário", None, None, None, None)
        self.achado_parcial = self._achado("ACH-AV-PAR", "Parcial da solução", "Despesas", Decimal("10.00"), None, None, None)
        self.achado_d = self._achado("ACH-AV-D", "Candidato ambíguo um", "Financeiro", Decimal("20.00"), self.regra_amb, self.ev3, self.exec_amb)
        self.achado_e = self._achado("ACH-AV-E", "Candidato ambíguo dois", "Financeiro", Decimal("20.00"), self.regra_amb, self.ev3, self.exec_amb)
        self.pre = self._pre()
        self.achado_secreto = Achado.objects.create(
            codigo="ACH-AV-SEC",
            prestacao_contas=self.prestacao,
            titulo=SEGREDO_IA,
            descricao_factual="Resultado automatizado que o modo cego não pode exibir.",
            chave_consolidacao="sec",
            categoria="Bancário",
            demonstracao=True,
        )

    def _regra(self, codigo, categoria, tipo=TipoExecucaoTecnica.DETERMINISTICA, capacidade=CapacidadeExecucao.AUTOMATICA):
        return RegraAnalise.objects.create(
            codigo=codigo,
            versao=1,
            categoria=categoria,
            titulo=f"Regra sintética {codigo}",
            descricao_original="Texto sintético.",
            tipo_execucao=tipo,
            capacidade=capacidade,
            executor="sintetico",
            ativa=True,
        )

    def _evidencia(self, codigo):
        return Evidencia.objects.create(
            codigo=codigo,
            prestacao_contas=self.prestacao,
            tipo=TipoEvidencia.DOCUMENTAL,
            documento=self.documento,
            metodo_obtencao=MetodoObtencao.EXTRACAO,
            demonstracao=True,
        )

    def _execucao(self, regra, resultado, limitacao=""):
        return ExecucaoRegra.objects.create(
            analise=self.analise,
            regra=regra,
            resultado_funcional=resultado,
            status_tecnico=StatusTecnico.SUCESSO,
            limitacao=limitacao,
            snapshot={"codigo": regra.codigo, "versao": regra.versao},
        )

    def _achado(self, codigo, titulo, categoria, materialidade, regra, evidencia, execucao):
        achado = Achado.objects.create(
            codigo=codigo,
            prestacao_contas=self.prestacao,
            analise=self.analise,
            titulo=titulo,
            descricao_factual=titulo,
            categoria=categoria,
            materialidade_financeira=materialidade,
            chave_consolidacao=codigo,
            demonstracao=True,
        )
        if regra is not None:
            AchadoRegra.objects.create(achado=achado, regra=regra, execucao=execucao, versao_regra=regra.versao)
        if evidencia is not None:
            AchadoEvidencia.objects.create(achado=achado, evidencia=evidencia, papel=PapelEvidencia.SUPORTA)
        return achado

    def _pre(self):
        pre = PreAnaliseTecnica.objects.create(
            codigo="PA-AV-1",
            prestacao_contas=self.prestacao,
            execucao_analise=self.analise,
            versao=1,
            status=StatusPreAnalise.CONGELADA,
            titulo="Pré-análise sintética",
            resumo_executivo="Síntese sem conclusão administrativa.",
            escopo="Escopo sintético.",
            limitacoes="Há limitação registrada.",
            encaminhamento="submeter_ao_auditor",
            hash_conteudo="d" * 64,
            congelada_em=timezone.now(),
            demonstracao=True,
        )
        secao = SecaoPreAnalise.objects.create(pre_analise=pre, tipo=TipoSecao.ACHADOS_CONSTATACOES, ordem=1, titulo="Achados", origem_conteudo=OrigemConteudo.DETERMINISTICO)
        AfirmacaoPreAnalise.objects.create(secao=secao, ordem=1, tipo=TipoAfirmacao.ACHADO, texto_atual="Fato suportado.", status_validacao=StatusValidacaoAfirmacao.VALIDADA)
        AfirmacaoPreAnalise.objects.create(
            secao=secao,
            ordem=2,
            tipo=TipoAfirmacao.ACHADO,
            texto_atual="Fato rejeitado.",
            status_validacao=StatusValidacaoAfirmacao.REJEITADA,
            motivo_rejeicao="Fonte inexistente: EVD-999",
            exibir_oficial=False,
        )
        return pre

    def _ground_truth(self, modo=ModoGroundTruth.CEGO):
        ground_truth = criar_ground_truth(self.prestacao, self.auditor, modo, demonstracao=True)
        definir_regra(ground_truth, self.auditor, self.regra_tp, "DIVERGÊNCIA", True, "Mesmo resultado.")
        definir_regra(ground_truth, self.auditor, self.regra_div, "DIVERGÊNCIA", True, "O sistema registrou conforme.")
        definir_regra(ground_truth, self.auditor, self.regra_nv, "NÃO VERIFICÁVEL", True, "Permanece não verificável.")
        definir_regra(ground_truth, self.auditor, self.regra_nl, "NÃO LOCALIZADO", True, "Permanece não localizado.")
        definir_regra(ground_truth, self.auditor, self.regra_na, "NÃO APLICÁVEL", False, "Fora da aplicação.")
        definir_regra(ground_truth, self.auditor, self.regra_misto, "NÃO VERIFICÁVEL", True, "Não é não aplicável.")
        definir_regra(ground_truth, self.auditor, self.regra_amb, "DIVERGÊNCIA", True, "Ambíguo nos achados.")
        adicionar_achado(
            ground_truth,
            self.auditor,
            titulo="Referência com outro texto",
            fato="Fato estruturado.",
            categoria="Financeiro",
            materialidade=Decimal("50.00"),
            criticidade=CriticidadeReferencia.MEDIA,
            regras=[self.regra_tp],
            evidencias=[self.ev1],
            normas=[self.norma],
            trechos=[self.trecho],
        )
        adicionar_achado(
            ground_truth,
            self.auditor,
            titulo=FRASE,
            fato="Achado omitido pela análise.",
            categoria="Vedações",
            materialidade=Decimal("1500.00"),
            criticidade=CriticidadeReferencia.CRITICA,
            regras=[self.regra_div],
            evidencias=[self.ev2],
            documentos=[self.documento],
            normas=[self.norma],
            trechos=[self.trecho],
        )
        adicionar_achado(
            ground_truth,
            self.auditor,
            titulo="Referência parcial",
            categoria="Despesas",
            materialidade=Decimal("10.00"),
            criticidade=CriticidadeReferencia.BAIXA,
        )
        adicionar_achado(
            ground_truth,
            self.auditor,
            titulo="Referência ambígua",
            categoria="Financeiro",
            materialidade=Decimal("20.00"),
            regras=[self.regra_amb],
            evidencias=[self.ev3],
        )
        adicionar_achado(
            ground_truth,
            self.auditor,
            titulo="Sem materialidade",
            categoria="Prazo",
            materialidade=None,
            criticidade=CriticidadeReferencia.BAIXA,
        )
        return self._congelar(ground_truth)

    def _congelar(self, ground_truth):
        enviar_validacao(ground_truth, self.auditor)
        validar(ground_truth, self.auditor)
        return congelar(ground_truth, self.auditor)

    def _avaliar(self, ground_truth):
        avaliacao = criar_avaliacao(self.pre, ground_truth, self.auditor, demonstracao=True)
        executar_avaliacao_task(avaliacao.pk, self.auditor.pk)
        avaliacao.refresh_from_db()
        return avaliacao


class TesteIsolamento(BaseAvaliacao):
    def test_ground_truth_nao_entra_na_geracao_nem_no_rag(self):
        ground_truth = self._ground_truth()
        contexto = montar_contexto(self.analise)
        bruto = json.dumps(contexto, ensure_ascii=False)
        self.assertNotIn(FRASE, bruto)
        self.assertNotIn("ground_truth", contexto)

        class Contexto:
            documentos = []
            prestacao = self.prestacao

            def resolucao_normativa(self):
                return None

        preparado = preparar_contexto(self.regra_tp, Contexto(), extras={"ground_truth": FRASE, "resultado_tecnico_conhecido": FRASE})
        self.assertNotIn(FRASE, json.dumps(preparado, ensure_ascii=False))
        self.assertIn("ground_truth", preparado["ground_truth_descartado"])
        raiz = Path(__file__).resolve().parents[1]
        for relativo in ("regras/motor.py", "pareceres/agente.py", "pareceres/contexto.py", "pareceres/gerador.py", "normas/recuperador.py", "achados/gerador.py"):
            texto = (raiz / relativo).read_text(encoding="utf-8")
            self.assertNotIn("GroundTruthPrestacao", texto)
            self.assertNotIn("aplicacao.avaliacao", texto)
        self.assertFalse(TrechoNormativo.objects.filter(texto__icontains=FRASE).exists())
        self.assertTrue(ground_truth.dados_demonstracao)

    def test_ground_truth_nao_altera_analise_congelada(self):
        antes = {
            "execucao": self.exec_tp.resultado_funcional,
            "evidencia": self.ev1.trecho,
            "achado": self.achado_tp.titulo,
            "pre": self.pre.hash_conteudo,
            "atualizado": self.achado_tp.atualizado_em,
        }
        ground_truth = self._ground_truth()
        avaliacao = self._avaliar(ground_truth)
        self.exec_tp.refresh_from_db()
        self.ev1.refresh_from_db()
        self.achado_tp.refresh_from_db()
        self.pre.refresh_from_db()
        self.assertEqual(self.exec_tp.resultado_funcional, antes["execucao"])
        self.assertEqual(self.ev1.trecho, antes["evidencia"])
        self.assertEqual(self.achado_tp.titulo, antes["achado"])
        self.assertEqual(self.pre.hash_conteudo, antes["pre"])
        self.assertEqual(self.achado_tp.atualizado_em, antes["atualizado"])
        self.assertEqual(avaliacao.snapshot.pre_analise_id, self.pre.pk)
        self.assertEqual(avaliacao.snapshot.hash_pre_analise, self.pre.hash_conteudo)

    def test_avaliacao_oficial_exige_analise_congelada(self):
        self.pre.status = StatusPreAnalise.AGUARDANDO_REVISAO
        self.pre.save(update_fields=["status"])
        ground_truth = self._ground_truth()
        with self.assertRaises(ErroAvaliacao):
            criar_avaliacao(self.pre, ground_truth, self.auditor)
        self.assertEqual(AvaliacaoInteligenciaArtificial.objects.count(), 0)
        self.pre.refresh_from_db()
        self.assertEqual(self.pre.status, StatusPreAnalise.AGUARDANDO_REVISAO)


class TesteVersoesEHash(BaseAvaliacao):
    def test_congelados_imutaveis_e_hashes_estaveis(self):
        ground_truth = self._ground_truth()
        hash_gt = ground_truth.hash_conteudo
        self.assertEqual(len(hash_gt), 64)
        self.assertEqual(calcular_hash_ground_truth(ground_truth), hash_gt)
        with self.assertRaises(ErroAvaliacao):
            definir_regra(ground_truth, self.auditor, self.regra_sg, "CONFORME")
        seguinte = nova_versao(ground_truth, self.auditor)
        definir_regra(seguinte, self.auditor, self.regra_sg, "DIVERGÊNCIA")
        ground_truth.refresh_from_db()
        self.assertEqual(ground_truth.hash_conteudo, hash_gt)
        self.assertEqual(ground_truth.versao, 1)
        self.assertEqual(seguinte.versao, 2)
        self.assertNotEqual(seguinte.status, ground_truth.status)

        avaliacao = self._avaliar(ground_truth)
        self.client.force_login(self.auditor)
        self.client.get(reverse("avaliacao:detalhe", kwargs={"pk": avaliacao.pk}))
        avaliacao.refresh_from_db()
        if avaliacao.status != "concluida":
            for item in avaliacao.correspondencias.filter(classificacao=ClassificacaoCorrespondencia.PENDENTE_REVISAO):
                revisar_correspondencia(item, self.auditor, "marcar_parcial", justificativa="Revisão sintética.")
            avaliacao.refresh_from_db()
        congelar_avaliacao(avaliacao, self.auditor)
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.hash_conteudo, calcular_hash_avaliacao(avaliacao))
        primeiro = avaliacao.hash_conteudo
        self.client.get(reverse("avaliacao:detalhe", kwargs={"pk": avaliacao.pk}))
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.hash_conteudo, primeiro)
        with self.assertRaises(ErroAvaliacao):
            revisar_correspondencia(avaliacao.correspondencias.first(), self.auditor, "marcar_parcial")
        nova = nova_versao_avaliacao(avaliacao, ground_truth, self.auditor)
        self.assertNotEqual(nova.pk, avaliacao.pk)
        metricas_v1 = dict(avaliacao.metricas)
        executar_comparacao(nova, self.auditor)
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.metricas, metricas_v1)
        self.assertEqual(avaliacao.status, "congelada")
        outra = PreAnaliseTecnica.objects.create(
            codigo="PA-AV-2",
            prestacao_contas=self.prestacao,
            execucao_analise=self.analise,
            versao=2,
            status=StatusPreAnalise.CONGELADA,
            titulo="Outra versão",
            resumo_executivo="Outra síntese.",
            hash_conteudo="e" * 64,
            demonstracao=True,
        )
        avaliacao.snapshot.refresh_from_db()
        self.assertEqual(avaliacao.snapshot.pre_analise_id, self.pre.pk)
        self.assertEqual(avaliacao.snapshot.versao_pre_analise, 1)
        self.assertNotEqual(avaliacao.snapshot.hash_pre_analise, outra.hash_conteudo)


class TesteCenarioSintetico(BaseAvaliacao):
    def test_tp_fp_fn_parcial_pendente_metricas_e_drill_down(self):
        with patch("urllib.request.urlopen") as urlopen:
            ground_truth = self._ground_truth()
            avaliacao = self._avaliar(ground_truth)
            urlopen.assert_not_called()
        self.assertEqual(ground_truth.modo, ModoGroundTruth.CEGO)
        self.assertTrue(all(item.dados_demonstracao for item in (ground_truth, avaliacao)))
        classificacoes = list(avaliacao.correspondencias.values_list("classificacao", flat=True))
        self.assertIn(ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO, classificacoes)
        self.assertIn(ClassificacaoCorrespondencia.FALSO_POSITIVO, classificacoes)
        self.assertIn(ClassificacaoCorrespondencia.FALSO_NEGATIVO, classificacoes)
        self.assertIn(ClassificacaoCorrespondencia.CORRESPONDENCIA_PARCIAL, classificacoes)
        self.assertIn(ClassificacaoCorrespondencia.PENDENTE_REVISAO, classificacoes)
        positivo = avaliacao.correspondencias.get(classificacao=ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO)
        self.assertNotEqual(positivo.achado.titulo, positivo.ground_truth_achado.titulo)
        self.assertEqual(avaliacao.metricas["parciais"], 1)
        self.assertGreaterEqual(avaliacao.metricas["pendentes"], 1)
        self.assertEqual(avaliacao.metricas["tp"], 1)
        self.assertEqual(avaliacao.metricas["fp"], 1)
        self.assertEqual(Decimal(avaliacao.metricas["precisao"]), Decimal("0.5000"))
        self.assertEqual(Decimal(avaliacao.metricas["recall"]), Decimal("0.3333"))
        self.assertIsNotNone(avaliacao.metricas["f1"])
        totais = avaliacao.metricas["regras"]["totais"]
        self.assertGreater(totais["sem_ground_truth"], 0)
        self.assertGreater(totais["nao_aplicaveis"], 0)
        self.assertGreater(totais["nao_verificaveis"], 0)
        self.assertGreater(totais["nao_localizadas"], 0)
        self.assertGreater(totais["fora_escopo"], 0)
        self.assertIn("Financeiro", avaliacao.metricas["regras"]["por_categoria"])
        self.assertIn("deterministica", avaliacao.metricas["regras"]["por_executor"])
        divergente = avaliacao.comparacoes_regra.get(regra=self.regra_misto)
        self.assertFalse(divergente.concordante)
        self.assertNotEqual(divergente.resultado_sistema, divergente.resultado_ground_truth)
        concordante = avaliacao.comparacoes_regra.get(regra=self.regra_tp)
        self.assertTrue(concordante.concordante)
        self.assertEqual(concordante.resultado_sistema.casefold(), concordante.resultado_ground_truth.casefold())
        self.assertGreater(totais["concordantes"], 0)
        self.assertGreater(totais["divergentes"], 0)
        fn = avaliacao.correspondencias.select_related("ground_truth_achado").get(
            classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO,
            ground_truth_achado__criticidade=CriticidadeReferencia.CRITICA,
        )
        self.assertEqual(fn.ground_truth_achado.materialidade, Decimal("1500.00"))
        self.assertIsInstance(fn.ground_truth_achado.materialidade, Decimal)
        sem_valor = avaliacao.correspondencias.get(ground_truth_achado__titulo="Sem materialidade")
        self.assertIsNone(sem_valor.ground_truth_achado.materialidade)
        self.assertIsNotNone(avaliacao.metricas["materialidade_fn"]["total"])
        self.assertNotEqual(avaliacao.metricas["materialidade_fn"]["total"], "0.00")
        self.assertGreater(avaliacao.metricas["fn_criticos"], 0)
        self.assertEqual(avaliacao.metricas["proveniencia"]["motivos"]["fonte_inexistente"], 1)
        self.assertNotIn("Nota da IA", json.dumps(avaliacao.metricas))
        pendente = avaliacao.correspondencias.filter(classificacao=ClassificacaoCorrespondencia.PENDENTE_REVISAO).first()

        class Gerenciador:
            def executar(self, **kwargs):
                return {"classificacao": ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO}

        registrar_sugestao_semantica(pendente, Gerenciador())
        pendente.refresh_from_db()
        self.assertEqual(pendente.classificacao, ClassificacaoCorrespondencia.PENDENTE_REVISAO)
        revisar_correspondencia(pendente, self.auditor, "marcar_parcial", justificativa="Continua parcial.", observacao="Revisão registrada.")
        revisao = pendente.revisoes.get()
        self.assertEqual(revisao.classificacao_anterior, ClassificacaoCorrespondencia.PENDENTE_REVISAO)
        self.assertEqual(revisao.classificacao_posterior, ClassificacaoCorrespondencia.CORRESPONDENCIA_PARCIAL)
        self.assertEqual(revisao.usuario, self.auditor)
        self.assertIsNotNone(revisao.data_hora)
        self.client.force_login(self.auditor)
        pagina = self.client.get(reverse("avaliacao:falso_negativo", kwargs={"pk": avaliacao.pk, "correspondencia_pk": fn.pk}))
        self.assertContains(pagina, fn.ground_truth_achado.codigo)
        self.assertContains(pagina, "Crítica")
        self.assertContains(pagina, "1500")
        self.assertContains(pagina, self.regra_div.codigo)
        self.assertContains(pagina, self.ev2.codigo)
        self.assertContains(pagina, self.norma.titulo)
        self.assertContains(pagina, "Falso negativo crítico")
        self.assertContains(pagina, "Abrir a pré-análise original")
        self.assertContains(pagina, self.pre.codigo)
        detalhe = self.client.get(reverse("avaliacao:detalhe", kwargs={"pk": avaliacao.pk}))
        self.assertContains(detalhe, "Precisão")
        self.assertContains(detalhe, "Não disponível") if False else self.assertNotContains(detalhe, "Nota da IA")
        self.assertNotContains(detalhe, "Score geral")
        registros = RegistroAuditoria.objects.filter(evento=RegistroAuditoria.Evento.AVALIACAO_IA)
        self.assertTrue(registros.exists())
        for registro in registros:
            self.assertNotIn("sk-", json.dumps(registro.detalhes))
            self.assertNotIn("Authorization", json.dumps(registro.detalhes))

    def test_modo_cego_nao_expoe_resultado_da_ia(self):
        from aplicacao.avaliacao.views import contexto_construcao

        ground_truth = criar_ground_truth(self.prestacao, self.auditor, ModoGroundTruth.CEGO, demonstracao=True)
        self.client.force_login(self.auditor)
        pagina = self.client.get(reverse("avaliacao:ground_truth", kwargs={"pk": ground_truth.pk}))
        api = self.client.get(
            reverse("avaliacao:contexto_ground_truth", kwargs={"pk": ground_truth.pk}),
            {
                "incluir_resultado_ia": "1",
                "achados": "1",
                "pre_analise": str(self.pre.pk),
                "encaminhamento": "1",
                "metricas": "1",
                "correspondencias": "1",
                "tp": "1",
                "fp": "1",
                "fn": "1",
            },
        )
        self.assertContains(pagina, "Ground Truth — modo Cego")
        self.assertNotContains(pagina, SEGREDO_IA)
        self.assertNotContains(api, SEGREDO_IA)
        corpo = api.json()
        direto = contexto_construcao(ground_truth)
        for origem in (corpo, direto):
            self.assertEqual(set(origem), {"modo", "documentos", "normas"})
            for chave in ("achados", "pre_analises", "encaminhamento", "metricas", "correspondencias", "tp", "fp", "fn"):
                self.assertNotIn(chave, origem)
        texto = api.content.decode()
        self.assertNotIn(self.pre.resumo_executivo, texto)
        self.assertNotIn(self.pre.codigo, texto)
        self.assertNotIn(self.pre.encaminhamento, texto)
        self.assertNotIn("verdadeiro_positivo", texto)
        self.assertNotIn("falso_negativo", texto)
        assistido = criar_ground_truth(self.prestacao, self.auditor, ModoGroundTruth.ASSISTIDO, demonstracao=True)
        pagina_assistida = self.client.get(reverse("avaliacao:ground_truth", kwargs={"pk": assistido.pk}))
        self.assertContains(pagina_assistida, "modo Assistido")
        self.assertContains(pagina_assistida, SEGREDO_IA)

    def test_permissoes_de_congelamento(self):
        ground_truth = criar_ground_truth(self.prestacao, self.analista, ModoGroundTruth.CEGO, demonstracao=True)
        definir_regra(ground_truth, self.analista, self.regra_tp, "DIVERGÊNCIA")
        enviar_validacao(ground_truth, self.analista)
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.post(reverse("avaliacao:congelar_ground_truth", kwargs={"pk": ground_truth.pk})).status_code, 403)
        self.client.force_login(self.analista)
        self.assertEqual(self.client.post(reverse("avaliacao:validar_ground_truth", kwargs={"pk": ground_truth.pk})).status_code, 403)
        self.assertEqual(self.client.post(reverse("avaliacao:congelar_ground_truth", kwargs={"pk": ground_truth.pk})).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("avaliacao:congelar_ground_truth", kwargs={"pk": ground_truth.pk})).status_code, 403)
        validar(ground_truth, self.auditor)
        self.client.force_login(self.auditor)
        resposta = self.client.post(reverse("avaliacao:congelar_ground_truth", kwargs={"pk": ground_truth.pk}))
        self.assertEqual(resposta.status_code, 302)
        ground_truth.refresh_from_db()
        self.assertEqual(ground_truth.status, "congelado")
        avaliacao = self._avaliar(ground_truth)
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse("avaliacao:detalhe", kwargs={"pk": avaliacao.pk})).status_code, 200)
        self.assertEqual(self.client.post(reverse("avaliacao:criar_ground_truth"), {"prestacao": self.prestacao.pk, "modo": "cego"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("avaliacao:congelar", kwargs={"pk": avaliacao.pk})).status_code, 403)
        self.client.force_login(self.analista)
        self.assertEqual(self.client.post(reverse("avaliacao:congelar", kwargs={"pk": avaliacao.pk})).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("avaliacao:congelar", kwargs={"pk": avaliacao.pk})).status_code, 403)
        avaliacao.refresh_from_db()
        self.assertNotEqual(avaliacao.status, "congelada")

    def test_norma_revogada_nao_fundamenta(self):
        ground_truth = criar_ground_truth(self.prestacao, self.auditor, ModoGroundTruth.CEGO)
        with self.assertRaises(ErroAvaliacao):
            adicionar_achado(ground_truth, self.auditor, titulo="Inválido", normas=[self.norma_revogada])

    def test_ausencia_de_materialidade_nao_vira_zero(self):
        ground_truth = self._ground_truth()
        avaliacao = self._avaliar(ground_truth)
        resumo = materialidade_falsos_negativos(avaliacao.correspondencias.select_related("ground_truth_achado"))
        self.assertIsInstance(resumo["total"], Decimal)
        vazio = materialidade_falsos_negativos(avaliacao.correspondencias.none())
        self.assertIsNone(vazio["total"])
        self.assertIsNone(vazio["media"])
        self.assertIsNone(vazio["maior"])
