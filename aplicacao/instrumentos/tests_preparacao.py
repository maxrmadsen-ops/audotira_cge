from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.escolhas import MetodoClassificacao, MetodoExtracao, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.instrumentos.escolhas import EstadoPreparacao, StatusCampo
from aplicacao.normas.escolhas import SituacaoNorma
from aplicacao.instrumentos.models import CampoInstrumento, PreparacaoInstrumento, ReferenciaNormativaExtraida, TermoFomento
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
def dados_documento(referencia, nome, conteudo, **extras):
    dados = {
        "acao": "adicionar_documento",
        "referencia": referencia.pk,
        "natureza": "publicacao_original",
        "redacao": "original",
        "fonte": "Diário Oficial de teste",
        "identificacao": "Edição sintética",
        "data_obtencao": "2014-08-01",
        "arquivo": SimpleUploadedFile(nome, conteudo, content_type="application/pdf"),
    }
    dados.update(extras)
    return dados


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
        self.assertRedirects(
            self.client.get(reverse("instrumentos:preparacao", kwargs={"pk": self.prestacao.pk})),
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
        )

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
        self.assertRedirects(
            self.client.get(reverse("instrumentos:preparacao", kwargs={"pk": self.prestacao.pk})),
            reverse("prestacoes_contas:detalhe", kwargs={"pk": self.prestacao.pk}),
        )

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
        self.assertContains(pagina, "Documento pendente")
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
                        dados_documento(lei, "lei.pdf", b"%PDF-1.4\n%%EOF"),
                    )
        self.assertEqual(resposta.status_code, 302)
        atraso.assert_not_called()
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


class TesteConsolidacaoBaseNormativa(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username="adm-base", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ADMINISTRADOR)
        self.prestacao = PrestacaoContas.objects.create(numero_processo="SINT-BASE-001", analista_responsavel=self.admin)
        self.documento = Documento.objects.create(
            prestacao_contas=self.prestacao,
            nome_original="base.pdf",
            nome_armazenado="base.pdf",
            tipo_documento=TipoDocumento.TERMO,
            metodo_classificacao=MetodoClassificacao.ESTRUTURAL,
            hash_sha256="c" * 64,
        )
        self.termo = TermoFomento.objects.create(documento=self.documento, data_assinatura=date(2022, 5, 11), status_validacao="validado")
        self.campo = CampoInstrumento.objects.create(termo=self.termo, nome="objeto", rotulo="Objeto", valor_extraido="texto original", status=StatusCampo.VALIDADO, validado_por=self.admin)
        citacoes = [
            ("Decreto", "1196", "2017", "Decreto nº 1196/2017", 2, "trecho 1196"),
            ("Decreto", "1.196", "2017", "Decreto nº 1.196/2017", 3, "trecho 1.196"),
            ("Decreto", "1196", "2017", "Decreto nº1196/2017", 4, "trecho sem espaço"),
            ("Decreto", "127", "11", "Decreto nº 127/11", 5, "trecho ano curto"),
            ("Decreto", "127", "2011", "Decreto nº 127/2011", 6, "trecho ano longo"),
            ("Decreto", "3.298", "99", "Decreto nº 3.298/99", 7, "trecho 99"),
            ("Lei", "13.019", "2014", "Lei nº 13.019/2014", 8, "trecho lei"),
            ("Lei Complementar", "264", "2004", "Lei Complementar nº 264/2004", 9, "trecho lc"),
            ("Resolução", "100", "2016", "Resolução nº 100/2016", 10, "trecho resolucao"),
            ("Decreto", "307", "2003", "Decreto nº 307/2003", 11, "trecho 307"),
            ("Lei Federal", "8.666", "1993", "Lei Federal nº 8.666/1993", 12, "trecho 8666"),
        ]
        for tipo, numero, ano, texto, pagina, trecho in citacoes:
            ReferenciaNormativaExtraida.objects.create(
                termo=self.termo, tipo=tipo, numero=numero, ano=ano, texto=texto, pagina=pagina, trecho=trecho,
                esfera="federal" if tipo == "Lei Federal" else "",
            )
        TermoFomento.objects.filter(pk=self.termo.pk).update(congelado=True, hash_congelado="abc123", status_validacao="validado")
        self.termo.refresh_from_db()
        PreparacaoInstrumento.objects.create(prestacao=self.prestacao, documento=self.documento, estado=EstadoPreparacao.VALIDADO)

    def test_normaliza_equivalentes_sem_alterar_originais_e_sem_fundir_ambiguos(self):
        from aplicacao.instrumentos.base_normativa import consolidar_referencias, montar_linhas

        antes = list(self.termo.referencias_normativas.order_by("id").values_list("id", "texto", "ano", "pagina", "trecho"))
        linhas = montar_linhas(self.termo)
        self.assertEqual(self.termo.referencias_normativas.count(), 11)
        self.assertEqual(len(linhas), 8)
        decreto_127 = next(linha for linha in linhas if linha["numero"] == "127")
        self.assertEqual(decreto_127["ano"], "2011")
        self.assertEqual({item.ano for item in decreto_127["referencias"]}, {"11", "2011"})
        self.assertEqual({item.texto for item in decreto_127["referencias"]}, {"Decreto nº 127/11", "Decreto nº 127/2011"})
        self.assertEqual(list(self.termo.referencias_normativas.order_by("id").values_list("id", "texto", "ano", "pagina", "trecho")), antes)
        curto = ReferenciaNormativaExtraida.objects.create(termo=self.termo, tipo="Decreto", numero="50", ano="11", texto="Decreto nº 50/11", pagina=1, trecho="curto")
        ReferenciaNormativaExtraida.objects.create(termo=self.termo, tipo="Decreto", numero="50", ano="1911", texto="Decreto nº 50/1911", pagina=1, trecho="1911")
        ReferenciaNormativaExtraida.objects.create(termo=self.termo, tipo="Decreto", numero="50", ano="2011", texto="Decreto nº 50/2011", pagina=1, trecho="2011")
        grupos = consolidar_referencias(list(self.termo.referencias_normativas.filter(numero="50")))
        self.assertEqual(len(grupos), 3)
        ambiguo = next(grupo for grupo in grupos if any(item.pk == curto.pk for item in grupo["refs"]))
        self.assertTrue(ambiguo["ambigua"])
        self.assertEqual(curto.ano, "11")
        import tempfile

        from django.test import override_settings

        from aplicacao.normas.models import Norma

        self.client.force_login(self.admin)
        antes_normas = Norma.objects.count()
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(NORMAS_RAIZ=pasta):
                self.client.post(
                    reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
                    dados_documento(curto, "ambiguo.pdf", b"%PDF-1.4\nambiguo\n%%EOF"),
                )
        curto.refresh_from_db()
        self.assertEqual(Norma.objects.count(), antes_normas)
        self.assertIsNone(curto.norma_id)
        self.assertEqual(curto.ano, "11")

    def test_abertura_nao_grava_e_preserva_termo_congelado(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as consultas:
            pagina = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "8 normas identificadas no Termo de Fomento.")
        self.assertContains(pagina, "Nenhum documento normativo foi anexado.")
        self.assertContains(pagina, "Documento pendente")
        self.assertContains(pagina, "Não verificada")
        self.assertContains(pagina, "Adicionar documento oficial")
        self.assertContains(pagina, "Confirmar documento")
        self.assertNotContains(pagina, "Não identificado")
        self.assertContains(pagina, "Esfera")
        self.assertContains(pagina, "federal")
        self.assertNotContains(pagina, "Órgão emissor")
        self.assertContains(pagina, "Decreto nº 127/11")
        self.assertContains(pagina, "Decreto nº 127/2011")
        escritas = [
            consulta["sql"]
            for consulta in consultas.captured_queries
            if consulta["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
            and any(tabela in consulta["sql"] for tabela in ("instrumentos_", "normas_", "documentos_", "prestacoes_contas_"))
        ]
        self.assertEqual(escritas, [])
        self.termo.refresh_from_db()
        self.campo.refresh_from_db()
        self.assertTrue(self.termo.congelado)
        self.assertEqual(self.termo.hash_congelado, "abc123")
        self.assertEqual(self.campo.valor_extraido, "texto original")
        self.assertEqual(self.campo.status, StatusCampo.VALIDADO)

    def test_upload_validacao_vigencia_e_substituicao_sem_processar(self):
        import tempfile
        from unittest.mock import patch

        from django.test import override_settings

        from aplicacao.normas.models import TrechoNormativo

        self.client.force_login(self.admin)
        referencia = self.termo.referencias_normativas.get(texto="Decreto nº 127/11")
        usos = UsoInteligenciaArtificial.objects.count()
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(NORMAS_RAIZ=pasta):
                with patch("aplicacao.normas.tarefas.processar_norma_task.delay") as tarefa:
                    resposta = self.client.post(
                        reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
                        dados_documento(referencia, "decreto.pdf", b"%PDF-1.4\nprimeiro\n%%EOF"),
                    )
        self.assertEqual(resposta.status_code, 302)
        tarefa.assert_not_called()
        self.assertEqual(UsoInteligenciaArtificial.objects.count(), usos)
        self.assertEqual(TrechoNormativo.objects.count(), 0)
        referencia.refresh_from_db()
        par = self.termo.referencias_normativas.get(texto="Decreto nº 127/2011")
        self.assertEqual(referencia.ano, "11")
        self.assertEqual(par.ano, "2011")
        self.assertEqual(referencia.norma_id, par.norma_id)
        self.assertEqual(referencia.norma.versao, 1)
        self.assertEqual(referencia.norma.situacao, SituacaoNorma.NAO_VERIFICADA)
        self.assertIsNone(referencia.norma.inicio_vigencia)
        self.assertIsNone(referencia.validado_por_id)
        aguardando = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(aguardando, "Documento disponível — aguardando conferência")
        self.assertContains(aguardando, "Não verificada")
        self.client.post(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}), {"acao": "validar", "referencia": referencia.pk})
        referencia.refresh_from_db()
        self.assertEqual(referencia.validado_por, self.admin)
        self.assertIsNone(referencia.norma.inicio_vigencia)
        conferida = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(conferida, "Identificação conferida")
        self.assertContains(conferida, "Não verificada")
        self.client.post(
            reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
            {
                "acao": "informar_datas",
                "referencia": referencia.pk,
                "inicio_vigencia": "2011-01-01",
                "fim_vigencia": "2012-01-01",
                "fonte_documental": "Art. 1º do PDF informado pelo auditor",
            },
        )
        from aplicacao.normas.escolhas import EstadoVerificacaoVigencia
        from aplicacao.normas.models import VerificacaoVigencia

        referencia.norma.refresh_from_db()
        referencia.refresh_from_db()
        self.assertEqual(referencia.validado_por, self.admin)
        self.assertIsNone(referencia.norma.inicio_vigencia)
        self.assertEqual(referencia.norma.situacao, SituacaoNorma.NAO_VERIFICADA)
        registro = VerificacaoVigencia.objects.get(norma=referencia.norma)
        self.assertEqual(registro.estado, EstadoVerificacaoVigencia.DATAS_INFORMADAS)
        self.assertIsNone(registro.verificado_por_id)
        pagina = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(pagina, "Datas informadas")
        self.assertNotContains(pagina, "fora da vigência registrada")
        self.assertNotContains(pagina, "inaplicável")
        from aplicacao.normas.escolhas import SituacaoConferenciaDocumento
        from aplicacao.normas.models import DocumentoNormativo

        primeiro = referencia.norma.documentos.get()
        hash_anterior = primeiro.hash_sha256
        self.client.post(
            reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
            {"acao": "conferir_documento", "referencia": referencia.pk, "documento": primeiro.pk},
        )
        referencia.refresh_from_db()
        primeiro.refresh_from_db()
        self.assertEqual(referencia.validado_por, self.admin)
        self.assertEqual(primeiro.conferido_por, self.admin)
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(NORMAS_RAIZ=pasta):
                with patch("aplicacao.normas.tarefas.processar_norma_task.delay") as tarefa:
                    self.client.post(
                        reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}),
                        dados_documento(
                            referencia,
                            "compilacao.pdf",
                            b"%PDF-1.4\nsegundo\n%%EOF",
                            natureza="compilacao_atualizada",
                            redacao="indeterminada",
                            fonte="Câmara dos Deputados de teste",
                            identificacao="Compilação sintética",
                            limitacao="A data de corte não está declarada.",
                            data_obtencao="14/10/2026",
                        ),
                    )
        tarefa.assert_not_called()
        referencia.refresh_from_db()
        par.refresh_from_db()
        primeiro.refresh_from_db()
        self.assertEqual(referencia.norma.versao, 1)
        self.assertEqual(referencia.norma_id, par.norma_id)
        self.assertEqual(referencia.validado_por, self.admin)
        self.assertEqual(par.validado_por, self.admin)
        self.assertIsNone(referencia.norma.inicio_vigencia)
        self.assertFalse(referencia.norma.arquivo)
        atuais = list(DocumentoNormativo.objects.filter(norma=referencia.norma, substituido_em__isnull=True).order_by("id"))
        self.assertEqual(len(atuais), 2)
        self.assertEqual(primeiro.situacao_conferencia, SituacaoConferenciaDocumento.CONFERIDA)
        self.assertEqual(atuais[1].situacao_conferencia, SituacaoConferenciaDocumento.AGUARDANDO)
        self.assertIsNone(atuais[1].conferido_por_id)
        self.assertEqual(VerificacaoVigencia.objects.get(norma=referencia.norma).documento_id, primeiro.pk)
        self.assertEqual(VerificacaoVigencia.objects.get(norma=referencia.norma).hash_sha256, hash_anterior)
        self.assertEqual(atuais[1].data_obtencao, date(2026, 10, 14))
        self.assertEqual(TrechoNormativo.objects.count(), 0)
        preservado = RegistroAuditoria.objects.create(
            usuario=self.admin,
            evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
            descricao="Verificação histórica preservada",
            detalhes={
                "referencia": referencia.pk,
                "norma": referencia.norma_id,
                "versao": 1,
                "hash_sha256": "",
                "versao_documento": 1,
                "hash_documento": hash_anterior,
                "documento": primeiro.pk,
                "acao": "verificar_vigencia",
            },
        )
        convivem = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(convivem, "DD/MM/AAAA")
        self.assertNotContains(convivem, 'type="date"')
        self.assertContains(convivem, f"Documento {primeiro.pk} · versão 1 · hash {hash_anterior}")
        preservado.refresh_from_db()
        self.assertEqual(preservado.detalhes["hash_sha256"], "")
        self.assertEqual(preservado.detalhes["hash_documento"], hash_anterior)
        evidencia = RegistroAuditoria.objects.filter(detalhes__acao="informar_datas", detalhes__referencia=referencia.pk).order_by("-id").first()
        self.assertEqual(evidencia.detalhes["documento"], primeiro.pk)
        self.assertEqual(evidencia.detalhes["versao"], primeiro.versao)
        self.assertEqual(evidencia.detalhes["hash_sha256"], hash_anterior)
        self.assertContains(convivem, "Datas informadas")
        self.assertContains(convivem, "Publicação original")
        self.assertContains(convivem, "Compilação atualizada")
        self.assertContains(convivem, "2 documentos oficiais")
        self.assertContains(convivem, hash_anterior)
        evento = RegistroAuditoria.objects.filter(evento=RegistroAuditoria.Evento.CRIACAO, detalhes__referencia=referencia.pk).order_by("-data_hora").first()
        self.assertEqual(evento.detalhes["versao"], 1)
        self.assertEqual(evento.detalhes["hash_sha256"], atuais[1].hash_sha256)
        self.assertIn("situacao_anterior", evento.detalhes)
        self.assertIn("situacao_posterior", evento.detalhes)
        self.termo.refresh_from_db()
        self.campo.refresh_from_db()
        self.assertTrue(self.termo.congelado)
        self.assertEqual(self.campo.valor_extraido, "texto original")
        self.assertEqual(self.campo.status, StatusCampo.VALIDADO)

    def test_ux_e_permissoes_da_base(self):
        auditor = Usuario.objects.create_user(username="aud-base", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.AUDITOR)
        consulta = Usuario.objects.create_user(username="con-base", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.CONSULTA)
        alheio = Usuario.objects.create_user(username="ana-base-alheia", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ANALISTA)
        url = reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk})
        self.client.force_login(alheio)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(consulta)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(auditor)
        pagina = self.client.get(url)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Adicionar documento oficial")
        self.assertContains(pagina, "Confirmar documento")
        self.assertContains(pagina, 'class="anexo-arquivo"')
        self.client.post(url, {"acao": "validar", "referencia": self.termo.referencias_normativas.first().pk})
        self.termo.referencias_normativas.first().refresh_from_db()
        self.assertIsNone(self.termo.referencias_normativas.first().validado_por_id)

    def test_verificacao_humana_divergencia_historico_e_termo_congelado(self):
        import tempfile

        from django.db import connection
        from django.test import override_settings
        from django.test.utils import CaptureQueriesContext

        from aplicacao.normas.escolhas import EstadoVerificacaoVigencia
        from aplicacao.normas.models import AplicabilidadeNorma, VerificacaoVigencia
        from aplicacao.instrumentos.base_normativa import montar_linhas

        self.client.force_login(self.admin)
        referencia = self.termo.referencias_normativas.get(texto="Decreto nº 127/11")
        url = reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk})
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(NORMAS_RAIZ=pasta):
                self.client.post(
                    url,
                    dados_documento(referencia, "decreto.pdf", b"%PDF-1.4\nperiodo\n%%EOF"),
                )
                referencia.refresh_from_db()
                referencia.norma.situacao = SituacaoNorma.VIGENTE
                referencia.norma.inicio_vigencia = date(1999, 1, 1)
                referencia.norma.save(update_fields=["situacao", "inicio_vigencia", "atualizado_em"])
                catalogo = self.client.get(url)
                self.assertContains(catalogo, "Não verificada")
                self.assertNotContains(catalogo, "Vigência verificada")
                self.client.post(url, {"acao": "verificar_vigencia", "referencia": referencia.pk, "fundamentacao": "Sem período.", "data_referencia": "2024-06-01"})
                self.assertEqual(VerificacaoVigencia.objects.count(), 0)
                self.client.post(
                    url,
                    {
                        "acao": "informar_datas",
                        "referencia": referencia.pk,
                        "inicio_vigencia": "2011-01-01",
                        "fim_vigencia": "2012-01-01",
                        "fonte_documental": "Art. 2º do documento anexado",
                    },
                )
                self.client.post(url, {"acao": "verificar_vigencia", "referencia": referencia.pk, "fundamentacao": "", "data_referencia": "2024-06-01"})
                self.client.post(url, {"acao": "verificar_vigencia", "referencia": referencia.pk, "fundamentacao": "Conferência do art. 2º.", "data_referencia": ""})
                self.assertEqual(VerificacaoVigencia.objects.count(), 1)
                self.client.post(
                    url,
                    {
                        "acao": "verificar_vigencia",
                        "referencia": referencia.pk,
                        "fundamentacao": "O art. 2º informa o período. A data posterior do instrumento permanece em análise.",
                        "data_referencia": "2024-06-01",
                    },
                )
                referencia.norma.refresh_from_db()
                verificada = VerificacaoVigencia.objects.order_by("-id").first()
                self.assertEqual(verificada.estado, EstadoVerificacaoVigencia.VERIFICADA)
                self.assertEqual(verificada.verificado_por, self.admin)
                self.assertIsNotNone(verificada.verificado_em)
                self.assertEqual(str(verificada.data_referencia), "2024-06-01")
                self.assertEqual(verificada.versao_documento, 1)
                self.assertEqual(verificada.hash_sha256, referencia.norma.documentos.get().hash_sha256)
                self.assertEqual(verificada.documento_id, referencia.norma.documentos.get().pk)
                self.assertEqual(referencia.norma.situacao, SituacaoNorma.VIGENTE)
                self.assertEqual(str(referencia.norma.inicio_vigencia), "1999-01-01")
                self.assertEqual(AplicabilidadeNorma.objects.count(), 0)
                conferida = self.client.get(url)
                self.assertContains(conferida, "Vigência verificada")
                self.assertNotContains(conferida, "inaplicável")
                self.assertNotContains(conferida, "fora da vigência")
                self.client.post(url, {"acao": "validar", "referencia": referencia.pk})
                self.client.post(
                    url,
                    {
                        "acao": "registrar_divergencia_vigencia",
                        "referencia": referencia.pk,
                        "motivo_divergencia": "A data de referência está fora do período informado no art. 2º.",
                        "data_referencia": "2024-06-01",
                    },
                )
                divergencia = VerificacaoVigencia.objects.order_by("-id").first()
                self.assertEqual(divergencia.estado, EstadoVerificacaoVigencia.DIVERGENCIA)
                self.assertIn("fora do período", divergencia.motivo_divergencia)
                linha = next(item for item in montar_linhas(self.termo) if item["numero"] == "127")
                self.assertEqual(linha["indicador"], "azul")
                self.assertFalse(linha["inconsistente"])
                self.assertEqual(linha["vigencia"], "Divergência de vigência")
                pagina = self.client.get(url)
                self.assertContains(pagina, "Divergência de vigência")
                self.assertContains(pagina, "Identificação conferida")
                from aplicacao.normas.models import DocumentoNormativo

                documento = referencia.norma.documentos.get()
                self.client.post(url, {"acao": "conferir_documento", "referencia": referencia.pk, "documento": documento.pk})
                self.client.post(
                    url,
                    dados_documento(
                        referencia,
                        "outro.pdf",
                        b"%PDF-1.4\noutro\n%%EOF",
                        natureza="outro",
                        redacao="indeterminada",
                        fonte="Órgão oficial de teste",
                        identificacao="Outro documento oficial",
                    ),
                )
                outro = DocumentoNormativo.objects.get(identificacao="Outro documento oficial")
                hash_outro = outro.hash_sha256
                hash_anterior = documento.hash_sha256
                norma_id = referencia.norma_id
                self.client.post(
                    url,
                    {
                        "acao": "substituir_documento",
                        "referencia": referencia.pk,
                        "documento": documento.pk,
                        "arquivo": SimpleUploadedFile("decreto-v2.pdf", b"%PDF-1.4\nsubstituto\n%%EOF", content_type="application/pdf"),
                    },
                )
        referencia.refresh_from_db()
        documento.refresh_from_db()
        novo = DocumentoNormativo.objects.get(documento_anterior=documento)
        self.assertEqual(referencia.norma_id, norma_id)
        self.assertEqual(referencia.norma.versao, 1)
        self.assertEqual(referencia.validado_por, self.admin)
        self.assertEqual(novo.versao, 2)
        self.assertEqual(novo.documento_anterior_id, documento.pk)
        self.assertIsNotNone(documento.substituido_em)
        self.assertEqual(documento.conferido_por, self.admin)
        self.assertIsNone(novo.conferido_por_id)
        outro.refresh_from_db()
        self.assertIsNone(outro.substituido_em)
        self.assertEqual(outro.versao, 1)
        self.assertEqual(outro.hash_sha256, hash_outro)
        self.assertFalse(VerificacaoVigencia.objects.filter(documento=novo).exists())
        historico = list(VerificacaoVigencia.objects.filter(norma_id=norma_id).order_by("id"))
        self.assertEqual([item.estado for item in historico], [
            EstadoVerificacaoVigencia.DATAS_INFORMADAS,
            EstadoVerificacaoVigencia.VERIFICADA,
            EstadoVerificacaoVigencia.DIVERGENCIA,
        ])
        self.assertTrue(all(item.hash_sha256 == hash_anterior and item.versao_documento == 1 for item in historico))
        atual = self.client.get(url)
        self.assertContains(atual, "Não verificada")
        self.assertContains(atual, "O documento usado como evidência foi substituído.")
        self.assertContains(atual, hash_anterior)
        self.assertContains(atual, "O art. 2º informa o período.")
        self.assertEqual(self.termo.referencias_normativas.count(), 11)
        self.assertEqual(referencia.ano, "11")
        self.assertEqual(referencia.texto, "Decreto nº 127/11")
        antes = VerificacaoVigencia.objects.count()
        with CaptureQueriesContext(connection) as consultas:
            self.client.get(url)
        escritas = [
            consulta for consulta in consultas
            if consulta["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
            and any(tabela in consulta["sql"] for tabela in ("instrumentos_", "normas_", "documentos_", "prestacoes_contas_"))
        ]
        self.assertEqual(escritas, [])
        self.assertEqual(VerificacaoVigencia.objects.count(), antes)
        self.termo.refresh_from_db()
        self.campo.refresh_from_db()
        self.assertTrue(self.termo.congelado)
        self.assertEqual(self.termo.hash_congelado, "abc123")
        self.assertEqual(self.campo.valor_extraido, "texto original")
        self.assertEqual(self.campo.status, StatusCampo.VALIDADO)

    def test_documento_anterior_aparece_sem_converter_o_arquivo(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from aplicacao.instrumentos.escolhas import StatusCorrespondenciaNorma
        from aplicacao.normas.escolhas import TipoNorma
        from aplicacao.normas.models import DocumentoNormativo, Norma

        referencia = self.termo.referencias_normativas.get(texto="Lei nº 13.019/2014")
        norma = Norma.objects.create(
            tipo_norma=TipoNorma.LEI,
            numero="13.019",
            ano=2014,
            titulo="Lei citada no instrumento",
            situacao=SituacaoNorma.NAO_VERIFICADA,
            fonte="Cadastro anterior",
            arquivo="catalogo/anterior.pdf",
            nome_original="anterior.pdf",
            hash_sha256="d" * 64,
        )
        referencia.norma = norma
        referencia.status_correspondencia = StatusCorrespondenciaNorma.CORRESPONDENTE
        referencia.save(update_fields=["norma", "status_correspondencia"])
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as consultas:
            pagina = self.client.get(reverse("instrumentos:base_normativa", kwargs={"pk": self.prestacao.pk}))
        self.assertContains(pagina, "Documento anterior")
        self.assertContains(pagina, "Cadastro anterior")
        self.assertContains(pagina, "d" * 64)
        self.assertContains(pagina, "Não informada no registro anterior")
        self.assertContains(pagina, "disponível somente para leitura")
        self.assertEqual(DocumentoNormativo.objects.count(), 0)
        escritas = [
            consulta for consulta in consultas
            if consulta["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
            and any(tabela in consulta["sql"] for tabela in ("instrumentos_", "normas_", "documentos_", "prestacoes_contas_"))
        ]
        self.assertEqual(escritas, [])
        norma.refresh_from_db()
        referencia.refresh_from_db()
        self.assertEqual(norma.arquivo, "catalogo/anterior.pdf")
        self.assertEqual(norma.hash_sha256, "d" * 64)
        self.assertEqual(referencia.texto, "Lei nº 13.019/2014")
