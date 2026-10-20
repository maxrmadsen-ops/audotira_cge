"""Importação, inventário e processamento do laboratório documental (POC)."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.documentos.armazenamento import armazenar_pdf
from aplicacao.documentos.escolhas import (
    EtapaProcessamento,
    MetodoExtracao,
    OrigemDocumento,
    QualidadeExtracao,
    StatusProcessamento,
    TipoDocumento,
)
from aplicacao.documentos.extracao import ExtratorPDF
from aplicacao.documentos.models import Documento, PaginaDocumento
from aplicacao.laboratorio.classificacao import classificar_texto, detectar_numero_impresso, segmentar_regioes
from aplicacao.laboratorio.escolhas import (
    EstadoClassificacao,
    EstadoCampo,
    EstadoRevisao,
    PrioridadePendencia,
    StatusPendencia,
)
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.models import (
    CampoExtraido,
    InventarioPagina,
    LoteLaboratorio,
    PendenciaDocumental,
    RegiaoDocumental,
)
from aplicacao.laboratorio.vinculos import sugerir_vinculos


class ErroLaboratorio(Exception):
    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)


def importar_pdf(
    *,
    prestacao,
    caminho: Path | str,
    numero_processo_parcial: str,
    numero_instrumento: str = "",
    origem: str = "",
    usuario=None,
) -> LoteLaboratorio:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroLaboratorio("Arquivo PDF não encontrado no caminho informado.")
    conteudo = caminho.read_bytes()
    hash_sha256 = hashlib.sha256(conteudo).hexdigest()
    existente = LoteLaboratorio.objects.filter(hash_sha256=hash_sha256, prestacao_parceria=prestacao).first()
    if existente:
        return existente
    relativo = armazenar_pdf(prestacao.pk, conteudo)
    with transaction.atomic():
        documento = Documento.objects.create(
            prestacao_contas=prestacao,
            nome_original=caminho.name,
            nome_armazenado=relativo,
            tipo_documento=TipoDocumento.PRESTACAO_PARCIAL,
            classificacao_original=TipoDocumento.PRESTACAO_PARCIAL,
            tipo_sugerido=TipoDocumento.PRESTACAO_PARCIAL,
            mime_type="application/pdf",
            extensao="pdf",
            tamanho_bytes=len(conteudo),
            hash_sha256=hash_sha256,
            origem=OrigemDocumento.UPLOAD,
            status_processamento=StatusProcessamento.RECEBIDO,
            etapa=EtapaProcessamento.RECEBIDO,
            criado_por=usuario,
        )
        lote = LoteLaboratorio.objects.create(
            prestacao_parceria=prestacao,
            documento=documento,
            numero_processo_parcial=numero_processo_parcial,
            numero_instrumento=numero_instrumento,
            origem=origem or str(caminho),
            hash_sha256=hash_sha256,
            tamanho_bytes=len(conteudo),
            importado_por=usuario,
            limitacoes=(
                "IA externa desligada. Extração por texto nativo e OCR local. "
                "Resultados simulados não são gravados como evidência."
            ),
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.UPLOAD,
        descricao="Importação do PDF no laboratório documental",
        usuario=usuario,
        detalhes={
            "lote": lote.pk,
            "documento": documento.pk,
            "hash_sha256": hash_sha256,
            "tamanho_bytes": len(conteudo),
            "processo_parcial": numero_processo_parcial,
        },
    )
    return lote


def processar_lote(
    lote_id: int,
    usuario=None,
    *,
    com_ocr: bool = False,
    paginas_ocr: set[int] | None = None,
) -> LoteLaboratorio:
    """
    Inventaria todas as páginas.
    Por padrão usa somente texto nativo (rápido no PDF escaneado).
    OCR local entra quando com_ocr=True (todas) ou em paginas_ocr específicas.
    """
    lote = LoteLaboratorio.objects.select_related("documento").get(pk=lote_id)
    inicio = time.perf_counter()
    documento = lote.documento
    documento.status_processamento = StatusProcessamento.PROCESSANDO
    documento.etapa = EtapaProcessamento.EXTRAINDO_TEXTO
    documento.save(update_fields=["status_processamento", "etapa", "atualizado_em"])

    from aplicacao.documentos.armazenamento import ler_arquivo

    caminho = ler_arquivo(documento.nome_armazenado)
    if com_ocr and not paginas_ocr:
        extrator = ExtratorPDF()
        paginas = extrator.extrair(caminho)
    else:
        paginas = _extrair_inventario(caminho, paginas_ocr=paginas_ocr or set())
    falhas_ocr = sum(1 for pagina in paginas if pagina.get("erro_ocr"))
    if falhas_ocr:
        lote.limitacoes = (
            (lote.limitacoes + " " if lote.limitacoes else "")
            + f"OCR local falhou em {falhas_ocr} página(s)."
        ).strip()
    if not com_ocr and not paginas_ocr:
        lote.limitacoes = (
            (lote.limitacoes + " " if lote.limitacoes else "")
            + "Inventário inicial com texto nativo. OCR local seletivo nas páginas de amostra."
        ).strip()

    with transaction.atomic():
        documento.paginas.all().delete()
        lote.paginas.all().delete()
        lote.regioes.all().delete()
        lote.vinculos.all().delete()
        lote.pendencias.all().delete()

        PaginaDocumento.objects.bulk_create(
            [
                PaginaDocumento(
                    documento=documento,
                    numero_pagina=pagina["numero_pagina"],
                    texto_extraido=pagina["texto_extraido"],
                    metodo_extracao=pagina["metodo_extracao"],
                    qualidade_extracao=pagina["qualidade_extracao"],
                    necessitou_ocr=pagina["necessitou_ocr"],
                    ocr_executado=pagina["ocr_executado"],
                    quantidade_caracteres=pagina["quantidade_caracteres"],
                    dados_posicionais=pagina["dados_posicionais"],
                    erro_ocr=pagina["erro_ocr"],
                )
                for pagina in paginas
            ]
        )
        documento.quantidade_paginas = len(paginas)
        documento.status_processamento = StatusProcessamento.AGUARDANDO_VALIDACAO
        documento.etapa = EtapaProcessamento.AGUARDANDO_VALIDACAO
        documento.save(update_fields=["quantidade_paginas", "status_processamento", "etapa", "atualizado_em"])

        paginas_doc = {p.numero_pagina: p for p in documento.paginas.all()}
        inventarios = []
        regioes_criar = []
        campos_criar = []
        pendencias_criar = []

        for pagina in paginas:
            numero = pagina["numero_pagina"]
            texto = pagina["texto_extraido"] or ""
            candidatos = classificar_texto(texto)
            regioes = segmentar_regioes(texto, candidatos)
            estado_classificacao = (
                EstadoClassificacao.PROPOSTO if candidatos else EstadoClassificacao.INCONCLUSIVO
            )
            inventario = InventarioPagina(
                lote=lote,
                pagina_documento=paginas_doc.get(numero),
                numero_fisico=numero,
                numero_impresso=detectar_numero_impresso(texto),
                tipos_candidatos=[item["tipo"] for item in candidatos],
                quantidade_regioes=len(regioes),
                tem_texto_digital=pagina["metodo_extracao"] in {MetodoExtracao.NATIVO, MetodoExtracao.HIBRIDO}
                and pagina["quantidade_caracteres"] >= 40,
                tem_imagem=True,
                qualidade_extracao=pagina["qualidade_extracao"],
                legibilidade=_legibilidade(pagina),
                tecnica_utilizada=pagina["metodo_extracao"],
                tecnica_recomendada=_recomendar(pagina),
                estado_classificacao=estado_classificacao,
                estado_revisao=EstadoRevisao.PENDENTE,
                quantidade_caracteres=pagina["quantidade_caracteres"],
                trecho_amostra=(texto.strip()[:280] if texto.strip() else ""),
                proveniencia=f"pdf:{lote.hash_sha256[:16]}#page={numero}",
            )
            inventarios.append(inventario)

        InventarioPagina.objects.bulk_create(inventarios)
        inventarios_db = {p.numero_fisico: p for p in lote.paginas.all()}

        for pagina in paginas:
            numero = pagina["numero_pagina"]
            texto = pagina["texto_extraido"] or ""
            candidatos = classificar_texto(texto)
            regioes = segmentar_regioes(texto, candidatos)
            inventario = inventarios_db[numero]
            for regiao in regioes:
                obj = RegiaoDocumental(
                    lote=lote,
                    pagina=inventario,
                    tipo_documental=regiao["tipo"],
                    ordem=regiao["ordem"],
                    x=regiao["x"],
                    y=regiao["y"],
                    largura=regiao["largura"],
                    altura=regiao["altura"],
                    metodo_deteccao=regiao["metodo_deteccao"],
                    confianca=regiao["confianca"],
                    estado_classificacao=(
                        EstadoClassificacao.PROPOSTO
                        if regiao["tipo"] != "outros_nao_classificados"
                        else EstadoClassificacao.INCONCLUSIVO
                    ),
                )
                regioes_criar.append(obj)
            if pagina["qualidade_extracao"] in {QualidadeExtracao.AUSENTE, QualidadeExtracao.ILEGIVEL} or (
                pagina["quantidade_caracteres"] < 40 and pagina.get("erro_ocr")
            ):
                pendencias_criar.append(
                    PendenciaDocumental(
                        lote=lote,
                        pagina=inventario,
                        motivo="Texto insuficiente para classificação conclusiva nesta página.",
                        prioridade=PrioridadePendencia.MEDIA,
                        status=StatusPendencia.ABERTA,
                        historico=[{"evento": "abertura", "em": timezone.now().isoformat()}],
                    )
                )

        RegiaoDocumental.objects.bulk_create(regioes_criar)
        regioes_db = list(lote.regioes.select_related("pagina").all())
        por_pagina: dict[int, list[RegiaoDocumental]] = {}
        for regiao in regioes_db:
            por_pagina.setdefault(regiao.pagina.numero_fisico, []).append(regiao)

        for pagina in paginas:
            texto = pagina["texto_extraido"] or ""
            for regiao in por_pagina.get(pagina["numero_pagina"], []):
                for campo in extrair_campos(
                    regiao.tipo_documental,
                    texto,
                    pagina["numero_pagina"],
                    pagina["metodo_extracao"] or "nativo",
                ):
                    campos_criar.append(
                        CampoExtraido(
                            regiao=regiao,
                            esquema=campo["esquema"],
                            chave=campo["chave"],
                            rotulo=campo["rotulo"],
                            valor_original=campo["valor_original"],
                            valor_normalizado=campo["valor_normalizado"],
                            numero_pagina=campo["numero_pagina"],
                            trecho_evidencia=campo["trecho_evidencia"],
                            metodo=campo["metodo"],
                            estado_confianca=campo["estado_confianca"],
                            estado_revisao=EstadoCampo.AUSENTE if not campo["valor_original"] else EstadoCampo.PENDENTE,
                            obrigatorio=campo["obrigatorio"],
                        )
                    )
        CampoExtraido.objects.bulk_create(campos_criar)
        if pendencias_criar:
            PendenciaDocumental.objects.bulk_create(pendencias_criar)

        sugerir_vinculos(lote)

        duracao_ms = int((time.perf_counter() - inicio) * 1000)
        metodos = [p["metodo_extracao"] for p in paginas]
        predominante = max(set(metodos), key=metodos.count) if metodos else ""
        lote.quantidade_paginas = len(paginas)
        lote.processado_em = timezone.now()
        lote.duracao_processamento_ms = duracao_ms
        lote.tecnica_predominante = predominante
        lote.save(
            update_fields=[
                "quantidade_paginas",
                "processado_em",
                "duracao_processamento_ms",
                "tecnica_predominante",
                "limitacoes",
            ]
        )

    registrar_evento(
        evento=RegistroAuditoria.Evento.PROCESSAMENTO,
        descricao="Inventário e classificação do laboratório documental",
        usuario=usuario,
        detalhes={
            "lote": lote.pk,
            "paginas": lote.quantidade_paginas,
            "duracao_ms": lote.duracao_processamento_ms,
            "tecnica": lote.tecnica_predominante,
        },
    )
    return lote


def _extrair_inventario(caminho, paginas_ocr: set[int]) -> list[dict]:
    """Texto nativo em todas as páginas; OCR local somente nas páginas indicadas."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    from aplicacao.documentos.codificacao import decodificar_uso_privado
    from aplicacao.documentos.extracao import ErroExtracao
    from aplicacao.documentos.ocr import ServicoOCR
    from aplicacao.documentos.qualidade import avaliar_qualidade

    try:
        leitor = PdfReader(str(caminho))
    except PdfReadError as exc:
        raise ErroExtracao("O PDF está corrompido ou não pode ser lido.") from exc
    if getattr(leitor, "is_encrypted", False):
        raise ErroExtracao("PDF protegido por senha não é suportado nesta onda.")
    if not leitor.pages:
        raise ErroExtracao("O PDF não contém páginas.")
    ocr = ServicoOCR()
    resultado = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        try:
            texto_nativo = pagina.extract_text() or ""
        except Exception:
            texto_nativo = ""
        texto_nativo, _ = decodificar_uso_privado(texto_nativo)
        qualidade, necessita_ocr = avaliar_qualidade(texto_nativo)
        texto_final = texto_nativo
        metodo = MetodoExtracao.NATIVO if texto_nativo.strip() else MetodoExtracao.SEM_TEXTO
        ocr_executado = False
        erro_ocr = ""
        caixas: list[dict] = []
        if numero in paginas_ocr and necessita_ocr:
            try:
                texto_ocr, caixas = ocr.extrair_pagina(caminho, numero)
                ocr_executado = True
                if (texto_ocr or "").strip():
                    texto_final = texto_ocr
                    metodo = MetodoExtracao.OCR if not texto_nativo.strip() else MetodoExtracao.HIBRIDO
                    qualidade, _ = avaliar_qualidade(texto_final)
            except Exception as exc:
                erro_ocr = str(exc)[:300]
        resultado.append(
            {
                "numero_pagina": numero,
                "texto_extraido": texto_final,
                "metodo_extracao": metodo,
                "qualidade_extracao": qualidade,
                "necessitou_ocr": necessita_ocr,
                "ocr_executado": ocr_executado,
                "quantidade_caracteres": len(texto_final or ""),
                "dados_posicionais": {"caixas": caixas} if caixas else {},
                "erro_ocr": erro_ocr,
            }
        )
    return resultado


def ocr_paginas_lote(lote_id: int, numeros: list[int], usuario=None) -> LoteLaboratorio:
    """Reprocessa o lote aplicando OCR local apenas nas páginas informadas."""
    return processar_lote(lote_id, usuario=usuario, paginas_ocr=set(numeros))


def _legibilidade(pagina: dict) -> str:
    qualidade = pagina.get("qualidade_extracao")
    if qualidade == QualidadeExtracao.SUFICIENTE:
        return "legivel"
    if qualidade == QualidadeExtracao.ILEGIVEL:
        return "ilegivel"
    if pagina.get("erro_ocr"):
        return "ocr_indisponivel"
    if pagina.get("quantidade_caracteres", 0) < 40:
        return "texto_insuficiente"
    return "parcial"


def _recomendar(pagina: dict) -> str:
    if pagina.get("qualidade_extracao") == QualidadeExtracao.SUFICIENTE:
        return "texto_nativo"
    if pagina.get("ocr_executado"):
        return "revisao_humana"
    if pagina.get("erro_ocr"):
        return "ocr_local_ou_revisao_humana"
    return "ocr_local"


def montar_relatorio(lote: LoteLaboratorio) -> dict:
    paginas = list(lote.paginas.all())
    regioes = list(lote.regioes.all())
    campos = CampoExtraido.objects.filter(regiao__lote=lote)
    tipos = {}
    for regiao in regioes:
        tipos[regiao.tipo_documental] = tipos.get(regiao.tipo_documental, 0) + 1
    multiplas = sum(1 for pagina in paginas if pagina.quantidade_regioes > 1)
    classificadas = sum(
        1
        for pagina in paginas
        if pagina.estado_classificacao in {EstadoClassificacao.PROPOSTO, EstadoClassificacao.CONFIRMADO, EstadoClassificacao.CORRIGIDO}
        and pagina.tipos_candidatos
    )
    por_tecnica = {}
    for pagina in paginas:
        chave = pagina.tecnica_utilizada or "indefinida"
        por_tecnica[chave] = por_tecnica.get(chave, 0) + 1
    return {
        "paginas_inventariadas": len(paginas),
        "paginas_classificadas": classificadas,
        "paginas_multiplas_pecas": multiplas,
        "tipos_encontrados": tipos,
        "pecas_total": len(regioes),
        "pecas_confirmadas": sum(1 for r in regioes if r.estado_classificacao == EstadoClassificacao.CONFIRMADO),
        "pecas_pendentes": sum(1 for r in regioes if r.estado_revisao == EstadoRevisao.PENDENTE),
        "campos_extraidos": campos.exclude(valor_original="").count(),
        "campos_revisados": campos.filter(estado_revisao__in={EstadoCampo.CONFIRMADO, EstadoCampo.CORRIGIDO}).count(),
        "ilegivel_ou_ambiguo": lote.pendencias.filter(status=StatusPendencia.ABERTA).count(),
        "cobertura_tecnica": por_tecnica,
        "duracao_ms": lote.duracao_processamento_ms,
        "limitacoes": lote.limitacoes,
        "processo_parcial": lote.numero_processo_parcial,
        "processo_parceria": lote.prestacao_parceria.numero_processo,
        "instrumento": lote.numero_instrumento,
        "hash_sha256": lote.hash_sha256,
    }
