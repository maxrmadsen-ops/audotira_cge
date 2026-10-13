import hashlib
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.documentos.armazenamento import armazenar_pdf
from aplicacao.documentos.escolhas import MetodoExtracao, QualidadeExtracao, TipoDocumento
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.instrumentos.escolhas import EstadoPreparacao, StatusCampo
from aplicacao.instrumentos.models import CampoInstrumento, PreparacaoInstrumento, ReferenciaNormativaExtraida, TermoFomento
from aplicacao.prestacoes_contas.migracao_seletiva import ConflitoMigracao, exportar_processo, importar_processo
from aplicacao.prestacoes_contas.models import PrestacaoContas

CONTEUDO = b"%PDF-1.4 pacote-seletivo"


class TesteMigracaoSeletiva(TestCase):
    def setUp(self):
        self._temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporario.cleanup)
        self.override = override_settings(DOCUMENTOS_RAIZ=self._temporario.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        raiz = Path(self._temporario.name)
        Usuario = get_user_model()
        self.usuario = Usuario.objects.create_user(username="admin-mig", password="Isolada-apenas-no-teste", perfil=Usuario.Perfil.ADMINISTRADOR)
        self.demonstracao = PrestacaoContas.objects.create(numero_processo="SINT-MIG-DEMO", criado_por=self.usuario, demonstracao=True)
        self.prestacao = PrestacaoContas.objects.create(numero_processo="SINT-MIG-001", criado_por=self.usuario)
        relativo = armazenar_pdf(self.prestacao.pk, CONTEUDO)
        self.documento = Documento.objects.create(
            prestacao_contas=self.prestacao,
            nome_original="instrumento_sintetico.pdf",
            nome_armazenado=relativo,
            tipo_documento=TipoDocumento.TERMO,
            hash_sha256=hashlib.sha256(CONTEUDO).hexdigest(),
            tamanho_bytes=len(CONTEUDO),
            criado_por=self.usuario,
        )
        PaginaDocumento.objects.create(
            documento=self.documento,
            numero_pagina=1,
            texto_extraido="Texto já extraído.",
            metodo_extracao=MetodoExtracao.OCR,
            qualidade_extracao=QualidadeExtracao.SUFICIENTE,
            necessitou_ocr=True,
            ocr_executado=True,
        )
        self.termo = TermoFomento.objects.create(documento=self.documento, numero="100", ano=2024, status_validacao="validado")
        CampoInstrumento.objects.create(
            termo=self.termo,
            nome="municipio",
            rotulo="Município",
            valor_extraido="Cidade",
            valor_validado="Cidade",
            status=StatusCampo.VALIDADO,
            validado_por=self.usuario,
        )
        ReferenciaNormativaExtraida.objects.create(termo=self.termo, tipo="Lei", numero="1", ano="2024", texto="Lei nº 1/2024")
        PreparacaoInstrumento.objects.create(prestacao=self.prestacao, documento=self.documento, estado=EstadoPreparacao.VALIDADO)
        TermoFomento.objects.filter(pk=self.termo.pk).update(congelado=True, hash_congelado="a" * 64)
        RegistroAuditoria.objects.create(
            usuario=self.usuario,
            evento=RegistroAuditoria.Evento.VALIDACAO_INSTRUMENTO_CONCLUIDA,
            descricao="Validação concluída",
            detalhes={"prestacao": self.prestacao.pk, "documento": self.documento.pk},
        )
        self.destino = raiz / "pacote"

    def test_exporta_e_importa_sem_apagar_a_demonstracao(self):
        antes = PrestacaoContas.objects.count()
        exportar_processo("SINT-MIG-001", self.destino)
        self.assertEqual(PrestacaoContas.objects.count(), antes)
        PreparacaoInstrumento.objects.filter(prestacao=self.prestacao).delete()
        self.documento.delete()
        self.prestacao.delete()
        RegistroAuditoria.objects.all().delete()
        resultado = importar_processo(self.destino, aplicar=True)
        self.assertTrue(resultado["aplicado"])
        self.assertTrue(PrestacaoContas.objects.filter(pk=self.demonstracao.pk, numero_processo="SINT-MIG-DEMO").exists())
        restaurada = PrestacaoContas.objects.get(numero_processo="SINT-MIG-001")
        self.assertNotEqual(restaurada.pk, self.prestacao.pk)
        termo = TermoFomento.objects.get(documento__prestacao_contas=restaurada)
        self.assertTrue(termo.congelado)
        self.assertEqual(termo.hash_congelado, "a" * 64)
        campo = termo.campos.get(nome="municipio")
        self.assertEqual(campo.status, StatusCampo.VALIDADO)
        self.assertEqual(campo.validado_por, self.usuario)
        self.assertEqual(campo.valor_extraido, "Cidade")
        self.assertEqual(termo.referencias_normativas.count(), 1)
        self.assertEqual(restaurada.preparacao_instrumento.estado, EstadoPreparacao.VALIDADO)
        documento = restaurada.documentos.get()
        self.assertEqual(documento.hash_sha256, hashlib.sha256(CONTEUDO).hexdigest())
        self.assertEqual(documento.paginas.get().texto_extraido, "Texto já extraído.")
        evento = RegistroAuditoria.objects.get(evento=RegistroAuditoria.Evento.VALIDACAO_INSTRUMENTO_CONCLUIDA)
        self.assertEqual(evento.detalhes["prestacao"], restaurada.pk)
        self.assertEqual(evento.detalhes["documento"], documento.pk)
        with self.assertRaises(ConflitoMigracao):
            importar_processo(self.destino, aplicar=True)

    def test_usuario_ausente_interrompe_sem_gravar(self):
        exportar_processo("SINT-MIG-001", self.destino)
        PreparacaoInstrumento.objects.filter(prestacao=self.prestacao).delete()
        self.documento.delete()
        self.prestacao.delete()
        self.usuario.delete()
        with self.assertRaises(ConflitoMigracao) as erro:
            importar_processo(self.destino, aplicar=True)
        self.assertTrue(erro.exception.conflitos)
        self.assertFalse(PrestacaoContas.objects.filter(numero_processo="SINT-MIG-001").exists())
