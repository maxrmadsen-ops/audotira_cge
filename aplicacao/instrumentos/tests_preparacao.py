from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.escolhas import MetodoClassificacao, MetodoExtracao, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.instrumentos.escolhas import EstadoPreparacao, StatusCampo
from aplicacao.instrumentos.models import PreparacaoInstrumento
from aplicacao.instrumentos.preparacao import processar_instrumento, resumo_validacao, selecionar_documento
from aplicacao.instrumentos.servico import termo_do_documento
from aplicacao.inteligencia_artificial.models import UsoInteligenciaArtificial
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.models import Usuario

TEXTO = """
TERMO DE FOMENTO Nº 100/2024
Processo SGPe ABC 10/2024
CONCEDENTE: Estado de Exemplo, CNPJ 00.000.000/0001-91.
BENEFICIÁRIA: Entidade Sintética do município de OUTRO/SC, CNPJ 11.111.111/0001-11.
OBJETO: Apoio a atividade de exemplo, conforme Plano de Trabalho.
Valor total: R$ 1.200,00, em 02 parcelas de R$ 600,00.
CLÁUSULA PRIMEIRA — DO OBJETO
O objeto é o apoio descrito.
CLÁUSULA QUINTA — DA VIGÊNCIA
A vigência será de 6 meses a partir da assinatura.
Fundamentação: Lei nº 13.019/2014.
"""
PROIBIDOS = ("929", "2022TR0929", "SCC 3350", "Vargem", "APAE", "FCEE")
FONTES = (
    "aplicacao/instrumentos/extracao.py",
    "aplicacao/instrumentos/prompt_termo.py",
    "aplicacao/instrumentos/preparacao.py",
    "aplicacao/instrumentos/servico.py",
    "aplicacao/documentos/ficha.py",
    "aplicacao/documentos/classificacao.py",
    "aplicacao/instrumentos/conferencia.py",
    "aplicacao/instrumentos/views_preparacao.py",
    "aplicacao/instrumentos/esquema_partes.py",
    "aplicacao/instrumentos/estruturacao_partes.py",
    "aplicacao/instrumentos/unidade_identificacao.py",
    "aplicacao/instrumentos/enriquecimento.py",
    "aplicacao/instrumentos/base_normativa.py",
    "aplicacao/prestacoes_contas/migracao_seletiva.py",
)


class TestePreparacaoInstrumento(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username="adm-prep", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ADMINISTRADOR)
        self.auditor = Usuario.objects.create_user(username="aud-prep", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.AUDITOR)
        self.analista = Usuario.objects.create_user(username="ana-prep", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ANALISTA)
        self.alheio = Usuario.objects.create_user(username="ana-alheio", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ANALISTA)
        self.prestacao = PrestacaoContas.objects.create(numero_processo="SINT-PREP-001", analista_responsavel=self.analista)
        self.documento = Documento.objects.create(
            prestacao_contas=self.prestacao,
            nome_original="instrumento_sintetico.pdf",
            nome_armazenado="instrumento_sintetico.pdf",
            tipo_documento=TipoDocumento.TERMO,
            metodo_classificacao=MetodoClassificacao.ESTRUTURAL,
            hash_sha256="a" * 64,
        )
        PaginaDocumento.objects.create(
            documento=self.documento,
            numero_pagina=1,
            texto_extraido=TEXTO,
            metodo_extracao=MetodoExtracao.OCR,
            qualidade_extracao=QualidadeExtracao.SUFICIENTE,
            necessitou_ocr=True,
        )

    def test_analista_alheio_nao_acessa(self):
        self.client.force_login(self.alheio)
        resposta = self.client.get(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}))
        self.assertEqual(resposta.status_code, 403)
        self.client.force_login(self.analista)
        self.assertEqual(self.client.get(reverse("instrumentos:preparacao", kwargs={"pk": self.prestacao.pk})).status_code, 200)

    def test_fluxo_de_validacao_preserva_extraido_e_audita(self):
        usos = UsoInteligenciaArtificial.objects.count()
        self.client.force_login(self.analista)
        selecionar = self.client.post(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"acao": "selecionar", "documento": self.documento.pk},
        )
        self.assertEqual(selecionar.status_code, 302)
        processar = self.client.post(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"acao": "processar"},
        )
        self.assertEqual(processar.status_code, 302)
        termo = termo_do_documento(self.documento)
        self.assertEqual(termo.numero, "100")
        self.assertNotEqual(termo.numero, "929")
        self.assertEqual(UsoInteligenciaArtificial.objects.count(), usos)
        campo = termo.campos.get(nome="municipio")
        extraido = campo.valor_extraido
        self.assertTrue(campo.pagina or campo.trecho or extraido)
        if campo.pagina and campo.trecho:
            self.assertIn(campo.trecho[:40], TEXTO)
        pagina = self.client.get(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"pagina": campo.pagina or 1, "trecho": campo.trecho},
        )
        self.assertContains(pagina, "Ver origem")
        self.assertContains(pagina, "Piloto: revisão humana obrigatória")
        self.assertContains(pagina, "Tratar na Base Normativa")
        self.assertContains(pagina, "Base Normativa")
        retorno = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": campo.pk}),
            {"acao": "corrigir", "valor_validado": "Cidade revisada", "observacao": "Ajuste conferido no texto", "retorno": retorno},
        )
        campo.refresh_from_db()
        self.assertEqual(campo.valor_extraido, extraido)
        self.assertEqual(campo.valor_validado, "Cidade revisada")
        self.assertEqual(campo.status, StatusCampo.CORRIGIDO)
        outro = termo.campos.exclude(pk=campo.pk).first()
        self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": outro.pk}),
            {"acao": "nao_identificado", "retorno": retorno},
        )
        for pendente in termo.campos.filter(status=StatusCampo.AGUARDANDO):
            self.client.post(
                reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": pendente.pk}),
                {"acao": "confirmar", "retorno": retorno},
            )
        sem_justificativa = self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": campo.pk}),
            {"acao": "corrigir", "valor_validado": "Outra cidade", "retorno": retorno},
        )
        self.assertEqual(sem_justificativa.status_code, 302)
        campo.refresh_from_db()
        self.assertEqual(campo.valor_validado, "Cidade revisada")
        self._conferir_unidades(termo, self.analista)
        concluir = self.client.post(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"acao": "concluir", "ciente_ausencias": "1"},
        )
        self.assertEqual(concluir.status_code, 302)
        termo.refresh_from_db()
        self.assertTrue(termo.congelado)
        self.assertTrue(termo.hash_congelado)
        preparacao = PreparacaoInstrumento.objects.get(prestacao=self.prestacao)
        self.assertEqual(preparacao.estado, EstadoPreparacao.VALIDADO)
        self.assertGreater(resumo_validacao(termo)["identificadas"], 0)
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "reabrir"})
        termo.refresh_from_db()
        self.assertFalse(termo.congelado)
        self.assertEqual(termo.versao, 2)
        eventos = set(
            RegistroAuditoria.objects.filter(detalhes__prestacao=self.prestacao.pk).values_list("evento", flat=True)
        )
        for nome in (
            "instrumento_selecionado",
            "instrumento_processado",
            "instrumento_classificado",
            "campo_corrigido",
            "campo_nao_identificado",
            "campo_confirmado",
            "validacao_instrumento_concluida",
            "validacao_instrumento_reaberta",
        ):
            self.assertIn(nome, eventos)
        self.assertContains(self.client.get(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})), "Lei")

    def test_auditor_conclui_e_admin_ve(self):
        preparacao = PreparacaoInstrumento.objects.create(prestacao=self.prestacao, documento=self.documento)
        selecionar_documento(preparacao, self.documento, self.auditor)
        processar_instrumento(preparacao, self.auditor)
        termo = termo_do_documento(self.documento)
        self._conferir_unidades(termo, self.auditor)
        for campo in termo.campos.all():
            if campo.status not in {StatusCampo.VALIDADO, StatusCampo.CORRIGIDO}:
                campo.status = StatusCampo.VALIDADO
                campo.valor_validado = campo.valor_extraido
                campo.validado_por = self.auditor
                campo.save(update_fields=["status", "valor_validado", "validado_por"])
        self.client.force_login(self.auditor)
        resposta = self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "concluir"})
        self.assertEqual(resposta.status_code, 302)
        termo.refresh_from_db()
        self.assertTrue(termo.congelado)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("instrumentos:preparacao", kwargs={"pk": self.prestacao.pk})).status_code, 200)

    def test_upload_seleciona_sem_chamar_ia(self):
        self.client.force_login(self.analista)
        arquivo = SimpleUploadedFile("sintetico.pdf", b"%PDF-1.4 sintetico", content_type="application/pdf")
        recusa = self.client.post(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"acao": "enviar", "arquivo": arquivo},
        )
        self.assertEqual(recusa.status_code, 302)
        self.assertFalse(Documento.objects.filter(nome_original="sintetico.pdf").exists())
        arquivo = SimpleUploadedFile("sintetico.pdf", b"%PDF-1.4 sintetico", content_type="application/pdf")

        def pipeline_falso(documento_id, usuario_id=None, reprocessamento_id=None):
            documento = Documento.objects.get(pk=documento_id)
            documento.tipo_documento = TipoDocumento.TERMO
            documento.metodo_classificacao = MetodoClassificacao.ESTRUTURAL
            documento.save(update_fields=["tipo_documento", "metodo_classificacao"])
            PaginaDocumento.objects.get_or_create(
                documento=documento,
                numero_pagina=1,
                defaults={
                    "texto_extraido": TEXTO,
                    "metodo_extracao": MetodoExtracao.NATIVO,
                    "qualidade_extracao": QualidadeExtracao.SUFICIENTE,
                },
            )

        with patch("aplicacao.documentos.recebimento.processar_documento_task.delay"), patch(
            "aplicacao.instrumentos.preparacao.executar_pipeline", side_effect=pipeline_falso
        ):
            resposta = self.client.post(
                reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
                {"acao": "enviar", "arquivo": arquivo, "confirmar_envio": "1"},
            )
        self.assertEqual(resposta.status_code, 302)
        preparacao = PreparacaoInstrumento.objects.get(prestacao=self.prestacao)
        self.assertEqual(preparacao.estado, EstadoPreparacao.AGUARDANDO_VALIDACAO)
        self.assertEqual(UsoInteligenciaArtificial.objects.count(), 0)

    def test_codigo_generico_nao_traz_o_caso_piloto(self):
        raiz = Path(__file__).resolve().parents[2]
        for relativo in FONTES:
            texto = (raiz / relativo).read_text(encoding="utf-8")
            for marca in PROIBIDOS:
                self.assertNotIn(marca, texto, f"{relativo} contém {marca}")

    def test_abertura_consulta_dados_e_nao_chama_modelo(self):
        import inspect

        from aplicacao.instrumentos.views_preparacao import InstrumentoParceriaView

        self._processar()
        self.assertNotIn("enriquecer_instrumento", inspect.getsource(InstrumentoParceriaView.get))
        pagina = self.client.get(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "apenas consulta os dados já gravados")
        self.assertContains(pagina, "Estruturar atributos com o modelo")

    def _conferir_unidades(self, termo, usuario):
        from aplicacao.instrumentos.esquema_partes import confirmar_parte
        from aplicacao.instrumentos.unidade_identificacao import confirmar_identificacao
        from aplicacao.instrumentos.unidade_objeto import confirmar_unidade

        confirmar_unidade(termo, usuario)
        confirmar_identificacao(termo, usuario)
        for papel in termo.partes.values_list("papel", flat=True):
            confirmar_parte(termo, usuario, papel)

    def _processar(self, usuario=None):
        self.client.force_login(usuario or self.analista)
        self.client.post(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"acao": "selecionar", "documento": self.documento.pk},
        )
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "processar"})
        return termo_do_documento(self.documento)

    def test_tela_operacional_comeca_recolhida_para_os_tres_perfis(self):
        self._processar(self.admin)
        for usuario in (self.admin, self.auditor, self.analista):
            self.client.force_login(usuario)
            pagina = self.client.get(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}))
            self.assertEqual(pagina.status_code, 200)
            self.assertContains(pagina, "Visualizar PDF")
            self.assertContains(pagina, "Instrumento em análise")
            self.assertContains(pagina, "Validação do Instrumento da Parceria")
            self.assertContains(pagina, "A prestação de contas não é concluída")
            self.assertContains(pagina, "Gerenciar documento")
            self.assertContains(pagina, "Conferência das informações")
            self.assertContains(pagina, "Informações complementares")
            self.assertContains(pagina, "Confirmar todos os elegíveis")
            self.assertContains(pagina, "Confirmar elegíveis deste grupo")
            self.assertContains(pagina, "Detalhes técnicos")
            self.assertContains(pagina, "Evidências da classificação")
            self.assertContains(pagina, "Ver origem")
            self.assertContains(pagina, "Confirmar informação")
            self.assertContains(pagina, "Objeto e finalidade da parceria")
            self.assertContains(pagina, "Confirmar cláusula")
            self.assertContains(pagina, "Confirmar concedente")
            self.assertContains(pagina, "Confirmar identificação")
            self.assertContains(pagina, "Confirmar convenente")
            self.assertContains(pagina, "Não identificado no documento")
            self.assertContains(pagina, "Informações estruturadas")
            self.assertContains(pagina, "O objeto é o apoio descrito.")
            self.assertContains(pagina, "Valor extraído pelo sistema")
            self.assertContains(pagina, "Valor validado pelo auditor")
            self.assertContains(pagina, "Situação da conferência")
            self.assertContains(pagina, "Acompanhamento e análise das prestações")
            self.assertContains(pagina, "Encerramento e parecer final")
            self.assertContains(pagina, "A prestação de contas não é concluída")
            self.assertContains(pagina, 'data-filtro-botao="pendentes"')
            self.assertContains(pagina, 'data-filtro-botao="divergentes"')
            self.assertContains(pagina, "Piloto: revisão humana obrigatória")
            self.assertContains(pagina, 'aria-describedby="ajuda-conclusao" disabled')
            self.assertNotContains(pagina, 'class="grupo-conferencia" open')
            self.assertNotContains(pagina, "Trecho/evidência")
        self.client.force_login(self.alheio)
        self.assertEqual(self.client.get(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})).status_code, 403)
        negado = self.client.post(
            reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}),
            {"acao": "confirmar_lote", "escopo": "instrumento", "confirmar_lote": "1"},
        )
        self.assertEqual(negado.status_code, 403)

    def test_lote_preserva_extraido_correcao_ausencia_e_divergencia(self):
        termo = self._processar()
        retorno = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        municipio = termo.campos.get(nome="municipio")
        extraido_municipio = municipio.valor_extraido
        correcao = self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": municipio.pk}),
            {
                "acao": "corrigir",
                "valor_validado": "Cidade revisada",
                "observacao": "Ajuste conferido no texto",
                "retorno": retorno,
                "grupo": "identificacao-do-instrumento",
                "campo": "municipio",
            },
        )
        self.assertIn("grupo=identificacao-do-instrumento", correcao.url)
        self.assertIn("campo=municipio", correcao.url)
        permanencia = self.client.get(correcao.url)
        self.assertContains(permanencia, 'id="grupo-identificacao-do-instrumento" open')
        self.assertContains(permanencia, 'id="campo-municipio"')
        self.assertContains(permanencia, 'data-foco="1"')
        finalidade = termo.campos.get(nome="finalidade")
        self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": finalidade.pk}),
            {"acao": "nao_identificado", "retorno": retorno},
        )
        valor = termo.campos.get(nome="valor_total")
        valor.valor_extraido = "R$ 1.200,00"
        valor.valor_validado = ""
        valor.status = StatusCampo.AGUARDANDO
        valor.save(update_fields=["valor_extraido", "valor_validado", "status"])
        assinatura = termo.campos.get(nome="data_assinatura")
        assinatura.valor_extraido = "01/03/2024"
        assinatura.valor_validado = ""
        assinatura.status = StatusCampo.AGUARDANDO
        assinatura.save(update_fields=["valor_extraido", "valor_validado", "status"])
        termo.alerta_aritmetico = "Totais não fecham."
        termo.consistente_aritmeticamente = False
        termo.save(update_fields=["alerta_aritmetico", "consistente_aritmeticamente"])
        url = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        self.client.post(url, {"acao": "confirmar_lote", "escopo": "instrumento"})
        municipio.refresh_from_db()
        valor.refresh_from_db()
        self.assertEqual(municipio.status, StatusCampo.CORRIGIDO)
        self.assertEqual(valor.status, StatusCampo.AGUARDANDO)
        elegivel = (
            termo.campos.exclude(nome__in=["municipio", "finalidade", "valor_total", "parcelas", "objeto", "destinacao", "concedente", "beneficiario", "unidade_objeto_finalidade", "identificacao", "processo"])
            .exclude(nome__startswith="parte_")
            .exclude(valor_extraido="")
            .exclude(status=StatusCampo.NAO_IDENTIFICADO)
            .order_by("nome")
            .first()
        )
        self.assertIsNotNone(elegivel)
        extraido_elegivel = elegivel.valor_extraido
        self.client.force_login(self.auditor)
        grupo = self.client.post(
            url,
            {"acao": "confirmar_lote", "escopo": "grupo", "confirmar_lote": "1", "campo": [elegivel.nome, municipio.nome, valor.nome]},
        )
        self.assertEqual(grupo.status_code, 302)
        elegivel.refresh_from_db()
        municipio.refresh_from_db()
        valor.refresh_from_db()
        self.assertEqual(elegivel.status, StatusCampo.VALIDADO)
        self.assertEqual(elegivel.valor_validado, extraido_elegivel)
        self.assertEqual(elegivel.valor_extraido, extraido_elegivel)
        self.assertEqual(elegivel.validado_por, self.auditor)
        self.assertIsNotNone(elegivel.validado_em)
        self.assertEqual(municipio.valor_validado, "Cidade revisada")
        self.assertEqual(municipio.valor_extraido, extraido_municipio)
        self.assertEqual(valor.status, StatusCampo.AGUARDANDO)
        self.assertEqual(valor.valor_validado, "")
        self.client.force_login(self.admin)
        self.client.post(url, {"acao": "confirmar_lote", "escopo": "instrumento", "confirmar_lote": "1"})
        finalidade.refresh_from_db()
        valor.refresh_from_db()
        municipio.refresh_from_db()
        self.assertEqual(finalidade.status, StatusCampo.NAO_IDENTIFICADO)
        self.assertEqual(valor.status, StatusCampo.AGUARDANDO)
        self.assertEqual(municipio.status, StatusCampo.CORRIGIDO)
        evento = RegistroAuditoria.objects.filter(
            evento="campo_confirmado",
            detalhes__prestacao=self.prestacao.pk,
            detalhes__campo=elegivel.nome,
            detalhes__modalidade="lote_grupo",
        ).get()
        self.assertEqual(evento.detalhes["valor_extraido"], extraido_elegivel)
        self.assertEqual(evento.detalhes["valor_validado"], extraido_elegivel)
        self.assertEqual(evento.detalhes["versao"], termo.versao)
        self.assertEqual(evento.usuario, self.auditor)
        individual = RegistroAuditoria.objects.filter(
            evento="campo_corrigido",
            detalhes__campo="municipio",
            detalhes__prestacao=self.prestacao.pk,
        ).get()
        self.assertEqual(individual.detalhes["modalidade"], "individual")

    def test_ausencia_de_ocr_nao_marca_grupo_como_conferido(self):
        from django.utils import timezone

        from aplicacao.instrumentos.conferencia import montar_grupos, progresso
        from aplicacao.instrumentos.preparacao import resumo_validacao

        termo = self._processar()
        for campo in termo.campos.all():
            campo.status = StatusCampo.NAO_IDENTIFICADO
            campo.validado_por = None
            campo.validado_em = None
            campo.save(update_fields=["status", "validado_por", "validado_em"])
        grupos = montar_grupos(termo)
        self.assertTrue(grupos)
        for grupo in grupos:
            if not grupo["quantidade"]:
                continue
            if grupo.get("consolidada"):
                self.assertEqual(grupo["situacao"], "Pendente")
            else:
                self.assertEqual(grupo["situacao"], "Aguardando conferência")
        identificacao = next(grupo for grupo in grupos if grupo["ancora"] == "identificacao-do-instrumento")
        for campo in identificacao["campos"]:
            campo.validado_por = self.analista
            campo.validado_em = timezone.now()
            campo.save(update_fields=["validado_por", "validado_em"])
        revisado = termo.campos.exclude(nome__in=[campo.nome for campo in identificacao["campos"]]).exclude(status=StatusCampo.NAO_IDENTIFICADO).first()
        if revisado is None:
            revisado = termo.campos.exclude(nome__in=[campo.nome for campo in identificacao["campos"]]).first()
        revisado.status = StatusCampo.VALIDADO
        revisado.valor_validado = revisado.valor_extraido
        revisado.validado_por = self.analista
        revisado.save(update_fields=["status", "valor_validado", "validado_por"])
        from aplicacao.instrumentos.unidade_identificacao import confirmar_identificacao

        confirmar_identificacao(termo, self.analista)
        grupos = montar_grupos(termo)
        identificacao = next(grupo for grupo in grupos if grupo["ancora"] == "identificacao-do-instrumento")
        self.assertEqual(identificacao["situacao"], "Conferido")
        self.assertEqual(identificacao["classe"], "grupo-conferido")
        parcial = next(grupo for grupo in grupos if grupo["ancora"] != "identificacao-do-instrumento" and grupo["quantidade"])
        self.assertIn(parcial["situacao"], {"Em conferência", "Aguardando conferência", "Divergência", "Pendente", "Validada", "Corrigida"})
        resumo = progresso(resumo_validacao(termo))
        self.assertEqual(resumo["total"], resumo["revisados"] + resumo["pendentes"] + resumo["nao_identificadas"])
        self.assertLess(resumo["percentual"], 100)
        self.assertEqual(resumo["percentual"], round(100 * resumo["revisados"] / resumo["total"]))

    def test_destino_conferencia_ignora_parametro_invalido(self):
        from django.test import RequestFactory

        from aplicacao.instrumentos.conferencia import destino_conferencia

        pedido = RequestFactory().post("/", {"grupo": "../admin", "campo": "municipio", "filtro": "pendentes"})
        url = destino_conferencia("/instrumentos/", pedido)
        self.assertNotIn("..", url)
        self.assertIn("campo=municipio", url)
        self.assertIn("filtro=pendentes", url)

    def test_reprocessar_congelado_preserva_versao_e_lote_nao_altera(self):
        preparacao = PreparacaoInstrumento.objects.create(prestacao=self.prestacao, documento=self.documento)
        selecionar_documento(preparacao, self.documento, self.admin)
        processar_instrumento(preparacao, self.admin)
        termo = termo_do_documento(self.documento)
        for campo in termo.campos.all():
            campo.status = StatusCampo.VALIDADO
            campo.valor_validado = campo.valor_extraido
            campo.save(update_fields=["status", "valor_validado"])
        self.client.force_login(self.admin)
        situacao = self.prestacao.situacao
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "confirmar_unidade"})
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "confirmar_parte", "papel": "concedente"})
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "confirmar_parte", "papel": "beneficiario"})
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "confirmar_identificacao"})
        self.client.post(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}), {"acao": "concluir"})
        termo.refresh_from_db()
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.situacao, situacao)
        antes = termo.versoes_congeladas.count()
        digest = termo.hash_congelado
        url = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        self.client.post(url, {"acao": "processar", "reprocessar": "1"})
        self.client.post(url, {"acao": "processar", "reprocessar": "1", "confirmar_reprocessar": "1"})
        self.client.post(url, {"acao": "confirmar_lote", "escopo": "instrumento", "confirmar_lote": "1"})
        termo.refresh_from_db()
        self.assertTrue(termo.congelado)
        self.assertEqual(termo.hash_congelado, digest)
        self.assertEqual(termo.versoes_congeladas.count(), antes)

    def test_clausula_de_objeto_e_uma_unidade_e_preserva_atributos(self):
        from aplicacao.instrumentos.conferencia import montar_grupos
        from aplicacao.instrumentos.unidade_objeto import NOME_UNIDADE, progresso_da_conferencia, unidade_elegivel_lote

        termo = self._processar()
        objeto = termo.campos.get(nome="objeto")
        finalidade = termo.campos.get(nome="finalidade")
        destinacao = termo.campos.get(nome="destinacao")
        extraido_objeto = objeto.valor_extraido
        self.client.force_login(self.analista)
        self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": objeto.pk}),
            {"acao": "confirmar", "retorno": reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})},
        )
        self.client.post(
            reverse("documentos:validar_campo_termo", kwargs={"pk": self.documento.pk, "campo_id": finalidade.pk}),
            {"acao": "nao_identificado", "retorno": reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})},
        )
        destinacao.valor_extraido = "Serão destinados recursos financeiros no montante de R$ 345"
        destinacao.status = StatusCampo.AGUARDANDO
        destinacao.save(update_fields=["valor_extraido", "status"])
        termo.valor_total_texto = "1.234.567,89"
        termo.save(update_fields=["valor_total_texto"])
        termo.refresh_from_db()
        self.assertFalse(unidade_elegivel_lote(termo))
        pagina = self.client.get(reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(pagina, "Objeto e finalidade da parceria")
        self.assertContains(pagina, "O objeto é o apoio descrito.")
        self.assertContains(pagina, "Informações estruturadas")
        self.assertContains(pagina, "Decisões anteriores dos atributos são conflitantes")
        url = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        self.client.post(url, {"acao": "confirmar_lote", "escopo": "instrumento", "confirmar_lote": "1", "grupo": "objeto-e-finalidade"})
        self.assertFalse(termo.campos.filter(nome=NOME_UNIDADE).exists())
        objeto.refresh_from_db()
        finalidade.refresh_from_db()
        destinacao.refresh_from_db()
        self.assertEqual(objeto.status, StatusCampo.VALIDADO)
        self.assertEqual(objeto.valor_extraido, extraido_objeto)
        self.assertEqual(finalidade.status, StatusCampo.NAO_IDENTIFICADO)
        self.assertEqual(destinacao.valor_extraido, "Serão destinados recursos financeiros no montante de R$ 345")
        self.assertEqual(destinacao.status, StatusCampo.AGUARDANDO)
        resposta = self.client.post(url, {"acao": "confirmar_unidade", "grupo": "objeto-e-finalidade"})
        self.assertEqual(resposta.status_code, 302)
        unidade = termo.campos.get(nome=NOME_UNIDADE)
        self.assertEqual(unidade.status, StatusCampo.VALIDADO)
        self.assertIn("O objeto é o apoio descrito.", unidade.valor_extraido)
        self.assertEqual(unidade.valor_validado, unidade.valor_extraido)
        self.assertEqual(unidade.validado_por, self.analista)
        objeto.refresh_from_db()
        destinacao.refresh_from_db()
        self.assertEqual(objeto.status, StatusCampo.VALIDADO)
        self.assertEqual(destinacao.status, StatusCampo.AGUARDANDO)
        evento = RegistroAuditoria.objects.filter(evento="campo_confirmado", detalhes__campo=NOME_UNIDADE, detalhes__prestacao=self.prestacao.pk).get()
        self.assertEqual(evento.detalhes["modalidade"], "individual")
        self.assertEqual(evento.detalhes["unidade"], "objeto_finalidade")
        self.assertIn("O objeto é o apoio descrito.", evento.detalhes["valor_extraido"])
        self.assertEqual(evento.usuario, self.analista)
        grupo = next(item for item in montar_grupos(termo) if item["consolidada"])
        self.assertEqual(grupo["quantidade"], 1)
        resumo = progresso_da_conferencia(termo)
        self.assertEqual(resumo["total"], resumo["revisados"] + resumo["pendentes"] + resumo["nao_identificadas"])
        self.assertLess(resumo["total"], termo.campos.exclude(nome=NOME_UNIDADE).count())
        self.client.post(url, {"acao": "divergir_unidade", "observacao": "O parágrafo não corresponde ao documento.", "grupo": "objeto-e-finalidade"})
        unidade.refresh_from_db()
        self.assertEqual(unidade.status, StatusCampo.REJEITADO)
        self.assertIn("O objeto é o apoio descrito.", unidade.valor_extraido)
        objeto.refresh_from_db()
        self.assertEqual(objeto.valor_validado, extraido_objeto)

    def test_parte_confirma_so_o_que_existe_e_preserva_correcao(self):
        from aplicacao.instrumentos.esquema_partes import (
            CHAVES_CONTRATO,
            atributo_ausente,
            esquema_parte,
            nome_atributo,
            parte_para_contrato,
        )

        termo = self._processar()
        parte = termo.partes.get(papel="beneficiario")
        contrato = parte_para_contrato(parte)
        self.assertEqual(set(contrato) - {"papel"}, set(CHAVES_CONTRATO))
        self.assertIsNone(contrato["logradouro"]["valor"])
        self.assertEqual(contrato["logradouro"]["situacao"], "nao_localizado")
        self.assertIn("interveniente", esquema_parte()["properties"]["papel"]["enum"])
        self.assertIsNone(atributo_ausente()["valor"])
        self.client.force_login(self.analista)
        url = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        pagina = self.client.get(url)
        self.assertContains(pagina, "Confirmar concedente")
        self.assertContains(pagina, "Confirmar convenente")
        self.assertNotContains(pagina, "Confirmar interveniente")
        self.assertContains(pagina, "Serão confirmados")
        agregado = termo.campos.get(nome="beneficiario")
        extraido_nome = agregado.valor_extraido
        self.client.post(url, {"acao": "confirmar_parte", "papel": "beneficiario", "grupo": "partes-envolvidas"})
        cnpj = termo.campos.get(nome=nome_atributo("beneficiario", "cnpj"))
        self.assertEqual(cnpj.status, StatusCampo.VALIDADO)
        self.assertEqual(cnpj.valor_validado, parte.cnpj)
        self.assertEqual(cnpj.validado_por, self.analista)
        self.assertFalse(termo.campos.filter(nome=nome_atributo("beneficiario", "bairro")).exists())
        self.assertFalse(termo.campos.filter(nome=nome_atributo("beneficiario", "endereco")).exists())
        agregado.refresh_from_db()
        self.assertEqual(agregado.valor_extraido, extraido_nome)
        self.assertNotEqual(agregado.status, StatusCampo.VALIDADO)
        self.client.post(
            url,
            {
                "acao": "corrigir_atributo_parte",
                "papel": "beneficiario",
                "chave": "sigla",
                "valor_validado": "SIGLA REVISADA",
                "observacao": "Ajuste do auditor.",
                "grupo": "partes-envolvidas",
            },
        )
        cnpj.refresh_from_db()
        sigla = termo.campos.get(nome=nome_atributo("beneficiario", "sigla"))
        self.assertEqual(cnpj.status, StatusCampo.VALIDADO)
        self.assertEqual(cnpj.valor_validado, parte.cnpj)
        self.assertEqual(sigla.status, StatusCampo.CORRIGIDO)
        self.assertEqual(sigla.valor_extraido, "")
        self.assertEqual(sigla.valor_validado, "SIGLA REVISADA")
        self.client.post(url, {"acao": "confirmar_parte", "papel": "beneficiario"})
        sigla.refresh_from_db()
        cnpj.refresh_from_db()
        self.assertEqual(sigla.valor_validado, "SIGLA REVISADA")
        self.assertEqual(cnpj.valor_validado, parte.cnpj)
        evento = RegistroAuditoria.objects.filter(
            evento="campo_confirmado",
            detalhes__campo="unidade_parte_beneficiario",
            detalhes__prestacao=self.prestacao.pk,
        ).get()
        chaves = [item["chave"] for item in evento.detalhes["atributos"]]
        self.assertIn("cnpj", chaves)
        self.assertNotIn("bairro", chaves)
        self.assertIn("bairro", evento.detalhes["ausentes"])
        self.assertEqual(evento.detalhes["modalidade"], "lote_unidade")
        self.assertEqual(evento.detalhes["versao"], termo.versao)
        self.assertEqual(evento.usuario, self.analista)

    def test_modelo_so_grava_trecho_literal_e_preserva_validacao(self):
        from django.test import override_settings

        from aplicacao.instrumentos.esquema_partes import listar_atributos, nome_atributo
        from aplicacao.instrumentos.estruturacao_partes import (
            PROMPT_SISTEMA,
            contexto_do_documento,
            estruturar_partes,
            validar_resposta_partes,
        )
        from aplicacao.inteligencia_artificial.preparacao import tamanho_contexto
        from aplicacao.instrumentos.models import CampoInstrumento
        from aplicacao.inteligencia_artificial.escolhas import StatusUso
        from aplicacao.inteligencia_artificial.gerenciador import ResultadoChamada
        from aplicacao.inteligencia_artificial.schema import SchemaInvalido

        termo = self._processar()
        fonte = (
            "CONCEDENTE: Instituto de Exemplo, com sede na Rua das Flores, nº 10, "
            "Bairro Centro, Município de OUTRO/SC, neste ato representado por seu Diretor Fulano de Tal."
        )
        pagina = self.documento.paginas.get()
        pagina.texto_extraido = fonte
        pagina.save(update_fields=["texto_extraido"])
        concedente = termo.partes.get(papel="concedente")
        cnpj_original = concedente.cnpj
        concedente.nome = fonte
        concedente.endereco = ""
        concedente.municipio = ""
        concedente.uf = ""
        concedente.representante_nome = ""
        concedente.representante_cargo = ""
        concedente.save()
        CampoInstrumento.objects.create(
            termo=termo,
            nome=nome_atributo("concedente", "razao_social"),
            rotulo="Razão social",
            valor_extraido=fonte,
            valor_validado="Nome já conferido",
            status=StatusCampo.VALIDADO,
            validado_por=self.analista,
        )
        with override_settings(IA_INTEGRACAO="desligada"):
            with self.assertRaises(ValueError):
                estruturar_partes(termo)
        concedente.refresh_from_db()
        self.assertEqual(concedente.nome, fonte)
        self.assertEqual(UsoInteligenciaArtificial.objects.count(), 0)
        with self.assertRaises(SchemaInvalido):
            validar_resposta_partes({"partes": "texto"}, fonte)
        texto = validar_resposta_partes(
            {"partes": [{"papel": "concedente", "endereco": "Rua das Flores, nº 10", "razao_social": {"valor": "Instituto de Exemplo"}}]},
            fonte,
        )
        self.assertEqual(texto["partes"][0]["atributos"]["endereco"], "Rua das Flores, nº 10")
        self.assertEqual(texto["partes"][0]["atributos"]["razao_social"], "Instituto de Exemplo")
        self.assertEqual(texto["rejeitados"], [])
        por_papel = validar_resposta_partes({"concedente": {"bairro": {"valor": "Centro"}}}, fonte)
        self.assertEqual(por_papel["partes"][0]["papel"], "concedente")
        self.assertEqual(por_papel["partes"][0]["atributos"]["bairro"], "Centro")
        inventado = validar_resposta_partes({"partes": [{"papel": "concedente", "endereco": "Rua Inventada"}]}, fonte)
        self.assertEqual(inventado["partes"][0]["atributos"]["endereco"], "")
        self.assertEqual(inventado["rejeitados"][0]["chave"], "endereco")
        self.assertIn("preâmbulo", PROMPT_SISTEMA)
        self.assertIn("chave valor", PROMPT_SISTEMA)
        longo = '"linha"\n' * 5000
        recorte = contexto_do_documento(longo, 12000)
        self.assertLessEqual(tamanho_contexto(recorte), 12000)
        self.assertTrue(longo.startswith(recorte["documento"]))
        self.assertEqual(contexto_do_documento("Instituto de Exemplo", 12000)["documento"], "Instituto de Exemplo")

        class ProvedorFalso:
            def executar(self, **kwargs):
                payload = kwargs["validador_schema"](
                    {
                        "partes": [
                            {
                                "papel": "concedente",
                                "razao_social": {"valor": "Instituto de Exemplo"},
                                "endereco": {"valor": "Rua das Flores, nº 10"},
                                "bairro": {"valor": "Centro"},
                                "municipio": {"valor": "OUTRO"},
                                "estado": {"valor": "SC"},
                                "representante_nome": {"valor": "Fulano de Tal"},
                                "representante_cargo": {"valor": "Diretor"},
                                "cnpj": {"valor": "99.999.999/0001-99"},
                                "sigla": None,
                                "logradouro": None,
                                "numero": None,
                                "complemento": None,
                                "cep": None,
                                "representante_cpf": None,
                            }
                        ]
                    }
                )
                return ResultadoChamada(resposta=payload, status=StatusUso.SUCESSO, provedor="openai", modelo="teste")

        resumo = estruturar_partes(termo, gerenciador=ProvedorFalso())
        concedente.refresh_from_db()
        self.assertEqual(concedente.nome, fonte)
        self.assertEqual(concedente.endereco, "Rua das Flores, nº 10")
        self.assertEqual(concedente.municipio, "OUTRO")
        self.assertEqual(concedente.uf, "SC")
        self.assertEqual(concedente.representante_nome, "Fulano de Tal")
        self.assertEqual(concedente.representante_cargo, "Diretor")
        self.assertEqual(concedente.cnpj, cnpj_original)
        bairro = termo.campos.get(nome=nome_atributo("concedente", "bairro"))
        self.assertEqual(bairro.valor_extraido, "Centro")
        self.assertEqual(bairro.status, StatusCampo.AGUARDANDO)
        self.assertIsNone(bairro.validado_por)
        chaves = {item["chave"] for item in resumo["aceitos"]}
        self.assertIn("endereco", chaves)
        self.assertNotIn("razao_social", chaves)
        self.assertNotIn("cnpj", chaves)
        self.assertEqual(resumo["rejeitados"], [{"papel": "concedente", "chave": "cnpj"}])
        linhas = listar_atributos(concedente, {bairro.nome: bairro})
        bairro_linha = next(linha for linha in linhas if linha["chave"] == "bairro")
        self.assertEqual(bairro_linha["extraido"], "Centro")
        self.assertEqual(bairro_linha["situacao"], "Pendente")

    def test_identificacao_e_uma_unidade_e_preserva_atributos(self):
        from aplicacao.instrumentos.conferencia import montar_grupos
        from aplicacao.instrumentos.unidade_identificacao import nome_atributo
        from aplicacao.instrumentos.unidade_objeto import progresso_da_conferencia

        termo = self._processar()
        processo = termo.campos.get(nome="processo")
        extraido_processo = processo.valor_extraido
        processo.status = StatusCampo.CORRIGIDO
        processo.valor_validado = "Processo já conferido"
        processo.validado_por = self.analista
        processo.save(update_fields=["status", "valor_validado", "validado_por"])
        self.client.force_login(self.analista)
        url = reverse("instrumentos:instrumento", kwargs={"pk": self.prestacao.pk})
        pagina = self.client.get(url)
        self.assertContains(pagina, "Confirmar identificação")
        self.assertContains(pagina, "Tipo de instrumento")
        self.assertContains(pagina, "Número do processo administrativo")
        self.assertContains(pagina, "Município da entidade convenente")
        self.assertContains(pagina, "Detalhes técnicos")
        antes = progresso_da_conferencia(termo)
        self.client.post(url, {"acao": "confirmar_identificacao", "grupo": "identificacao-do-instrumento"})
        tipo = termo.campos.get(nome=nome_atributo("tipo"))
        numero = termo.campos.get(nome=nome_atributo("numero"))
        self.assertEqual(tipo.status, StatusCampo.VALIDADO)
        self.assertEqual(tipo.validado_por, self.analista)
        self.assertEqual(tipo.valor_extraido, termo.tipo_instrumento)
        self.assertIn(termo.numero, numero.valor_validado)
        processo.refresh_from_db()
        self.assertEqual(processo.status, StatusCampo.CORRIGIDO)
        self.assertEqual(processo.valor_extraido, extraido_processo)
        self.assertEqual(processo.valor_validado, "Processo já conferido")
        self.client.post(
            url,
            {
                "acao": "corrigir_atributo_identificacao",
                "chave": "numero",
                "valor_validado": "100/2025",
                "observacao": "Ano conferido pelo auditor.",
                "grupo": "identificacao-do-instrumento",
            },
        )
        tipo.refresh_from_db()
        numero.refresh_from_db()
        self.assertEqual(tipo.valor_validado, termo.tipo_instrumento)
        self.assertEqual(numero.status, StatusCampo.CORRIGIDO)
        self.assertEqual(numero.valor_extraido, f"{termo.numero}/{termo.ano}")
        self.assertEqual(numero.valor_validado, "100/2025")
        grupo = next(item for item in montar_grupos(termo) if item["ancora"] == "identificacao-do-instrumento")
        self.assertEqual(grupo["quantidade"], 1)
        self.assertEqual(grupo["tipo"], "identificacao")
        resumo = progresso_da_conferencia(termo)
        self.assertEqual(resumo["total"], resumo["revisados"] + resumo["pendentes"] + resumo["nao_identificadas"])
        self.assertLess(resumo["total"], antes["total"] + 4)
        evento = RegistroAuditoria.objects.filter(
            evento="campo_confirmado",
            detalhes__campo="unidade_identificacao",
            detalhes__prestacao=self.prestacao.pk,
        ).get()
        self.assertEqual(evento.detalhes["modalidade"], "lote_unidade")
        self.assertEqual(evento.detalhes["versao"], termo.versao)
        self.assertEqual(evento.usuario, self.analista)
        from aplicacao.instrumentos.unidade_identificacao import CHAVES_LLM, interpretar_atributo

        fonte = self.documento.paginas.get().texto_extraido
        self.assertEqual(interpretar_atributo("100/2024", fonte)["situacao"], "pendente")
        self.assertEqual(interpretar_atributo("Cidade Inventada", fonte)["situacao"], "rejeitado")
        self.assertEqual(interpretar_atributo(None, fonte)["situacao"], "nao_localizado")
        self.assertEqual(CHAVES_LLM, ("tipo_instrumento", "numero_instrumento", "numero_processo", "municipio_convenente"))

    def test_enriquecimento_completa_literal_e_preserva_validacao(self):
        from django.test import override_settings

        from aplicacao.instrumentos.enriquecimento import enriquecer_grupos, enriquecer_instrumento
        from aplicacao.inteligencia_artificial.escolhas import StatusUso
        from aplicacao.inteligencia_artificial.gerenciador import ResultadoChamada

        termo = self._processar()
        inicio = termo.campos.get(nome="vigencia_inicio")
        destinacao = termo.campos.get(nome="destinacao")
        destinacao.valor_extraido = "R$ 1.200"
        destinacao.status = StatusCampo.AGUARDANDO
        destinacao.save(update_fields=["valor_extraido", "status"])
        objeto = termo.campos.get(nome="objeto")
        extraido_objeto = objeto.valor_extraido
        objeto.valor_validado = "Objeto já conferido"
        objeto.status = StatusCampo.VALIDADO
        objeto.validado_por = self.analista
        objeto.save(update_fields=["valor_validado", "status", "validado_por"])
        with override_settings(IA_INTEGRACAO="desligada"):
            self.assertIsNone(enriquecer_instrumento(termo))
            self.assertEqual(UsoInteligenciaArtificial.objects.count(), 0)

        class ProvedorFalso:
            def executar(self, **kwargs):
                payload = kwargs["validador_schema"](
                    {
                        "atributos": [
                            {"chave": "vigencia_inicio", "valor": "A vigência será de 6 meses a partir da assinatura."},
                            {"chave": "destinacao", "valor": "R$ 1.200,00"},
                            {"chave": "objeto", "valor": "O objeto é o apoio descrito."},
                            {"chave": "finalidade", "valor": "Texto inventado fora do documento"},
                        ]
                    }
                )
                return ResultadoChamada(resposta=payload, status=StatusUso.SUCESSO, provedor="openai", modelo="teste")

        resumo = enriquecer_grupos(termo, gerenciador=ProvedorFalso())
        inicio.refresh_from_db()
        destinacao.refresh_from_db()
        objeto.refresh_from_db()
        self.assertEqual(inicio.valor_extraido, "A vigência será de 6 meses a partir da assinatura.")
        self.assertEqual(inicio.status, StatusCampo.AGUARDANDO)
        self.assertIsNone(inicio.validado_por_id)
        self.assertEqual(destinacao.valor_extraido, "R$ 1.200,00")
        self.assertEqual(objeto.valor_extraido, extraido_objeto)
        self.assertEqual(objeto.valor_validado, "Objeto já conferido")
        aceitos = {item["chave"] for item in resumo["aceitos"]}
        self.assertIn("vigencia_inicio", aceitos)
        self.assertIn("destinacao", aceitos)
        self.assertNotIn("objeto", aceitos)
        self.assertIn("finalidade", {item["chave"] for item in resumo["rejeitados"]})

    def test_base_normativa_reusa_catalogo_e_nao_presume_vigencia(self):
        import tempfile
        from datetime import date
        from unittest.mock import patch

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        from aplicacao.instrumentos.escolhas import EstadoPreparacao
        from aplicacao.instrumentos.models import PreparacaoInstrumento, ReferenciaNormativaExtraida
        from aplicacao.normas.escolhas import SituacaoNorma, TipoNorma
        from aplicacao.normas.models import Norma

        termo = self._processar(self.admin)
        municipio = termo.campos.get(nome="municipio")
        extraido = municipio.valor_extraido
        preparacao = PreparacaoInstrumento.objects.get(prestacao=self.prestacao)
        preparacao.estado = EstadoPreparacao.VALIDADO
        preparacao.save(update_fields=["estado"])
        Norma.objects.create(
            tipo_norma=TipoNorma.DECRETO,
            numero="1.010",
            ano=2024,
            titulo="Decreto de exemplo",
            inicio_vigencia=date(2024, 1, 1),
            situacao=SituacaoNorma.VIGENTE,
            arquivo="catalogo/existente.pdf",
            hash_sha256="b" * 64,
        )
        ReferenciaNormativaExtraida.objects.create(termo=termo, tipo="Decreto", numero="1010", ano="2024", texto="Decreto nº 1010/2024")
        ReferenciaNormativaExtraida.objects.create(termo=termo, tipo="Decreto", numero="1.010", ano="2024", texto="Decreto nº 1.010/2024")
        antes = Norma.objects.count()
        self.client.force_login(self.alheio)
        self.assertEqual(self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk})).status_code, 403)
        self.client.force_login(self.admin)
        antes_refs = list(
            termo.referencias_normativas.order_by("id").values_list("id", "texto", "status_correspondencia", "norma_id")
        )
        pagina = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(pagina, "Documentos normativos necessários")
        self.assertContains(pagina, "Lei nº 13.019/2014")
        self.assertContains(pagina, "Documento necessário")
        self.assertContains(pagina, "Não verificada")
        self.assertEqual(pagina.content.decode().count("Decreto nº 1010/2024"), 1)
        self.assertEqual(Norma.objects.count(), antes)
        self.assertEqual(
            list(termo.referencias_normativas.order_by("id").values_list("id", "texto", "status_correspondencia", "norma_id")),
            antes_refs,
        )
        lei = termo.referencias_normativas.get(texto="Lei nº 13.019/2014")
        self.assertIsNone(lei.norma_id)
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(NORMAS_RAIZ=pasta):
                with patch("aplicacao.normas.tarefas.processar_norma_task.delay") as atraso:
                    resposta = self.client.post(
                        reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
                        {
                            "acao": "enviar_documento",
                            "referencia": lei.pk,
                            "arquivo": SimpleUploadedFile("lei.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
                        },
                    )
        self.assertEqual(resposta.status_code, 302)
        atraso.assert_called_once()
        lei.refresh_from_db()
        self.assertIsNotNone(lei.norma_id)
        self.assertIsNone(lei.norma.inicio_vigencia)
        self.assertEqual(lei.norma.situacao, SituacaoNorma.NAO_VERIFICADA)
        self.assertEqual(Norma.objects.count(), antes + 1)
        self.client.post(
            reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
            {"acao": "validar", "referencia": lei.pk},
        )
        lei.refresh_from_db()
        municipio.refresh_from_db()
        self.assertEqual(lei.validado_por, self.admin)
        self.assertEqual(municipio.valor_extraido, extraido)
        self.assertIsNone(termo.referencias_normativas.get(texto="Decreto nº 1.010/2024").norma_id)
