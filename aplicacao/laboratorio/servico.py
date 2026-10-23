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
from aplicacao.laboratorio.classificacao import (
    classificar_texto,
    detectar_numero_impresso,
    candidatos_da_peca,
    dividir_dispensa_e_transferencia,
    dividir_transferencia_e_holerite,
    recortar_texto_para_tipo,
    segmentar_regioes,
    tipo_principal,
)
from aplicacao.laboratorio.escolhas import (
    EstadoClassificacao,
    EstadoCampo,
    EstadoRevisao,
    PrioridadePendencia,
    StatusPendencia,
)
from aplicacao.laboratorio.extracao import (
    estruturar_rubricas,
    estruturar_rubricas_rescisao,
    extrair_campos,
    mesclar_rubricas_rescisao,
    normalizar_pontuacao_monetaria,
)
from aplicacao.laboratorio.localizacao import (
    caixa_da_rubrica,
    caixa_do_valor,
    faixa_abaixo,
    faixa_do_rotulo,
    localizar_campos,
    projetar_pagina,
)
from aplicacao.laboratorio.models import (
    CampoExtraido,
    InventarioPagina,
    LoteLaboratorio,
    PendenciaDocumental,
    RegiaoDocumental,
    RubricaExtraida,
)
from aplicacao.laboratorio.releitura import (
    aplicar_em_campos,
    decidir_autenticacao,
    decidir_data,
    decidir_matricula,
    reler_faixa,
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
            candidatos = candidatos_da_peca(classificar_texto(texto), texto)
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
            candidatos = candidatos_da_peca(classificar_texto(texto), texto)
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
            regioes_pagina = por_pagina.get(pagina["numero_pagina"], [])
            tipos_pagina = [r.tipo_documental for r in regioes_pagina]
            for regiao in regioes_pagina:
                texto_regiao = recortar_texto_para_tipo(texto, regiao.tipo_documental, tipos_pagina)
                if texto_regiao and texto_regiao != (regiao.texto_regiao or ""):
                    regiao.texto_regiao = texto_regiao[:20000]
                    regiao.save(update_fields=["texto_regiao"])
                for campo in extrair_campos(
                    regiao.tipo_documental,
                    texto_regiao,
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
    """Indicadores verificáveis. Inventário ≠ classificação integral."""
    from aplicacao.laboratorio.apresentacao import eh_placeholder

    paginas = list(lote.paginas.all())
    todas = list(lote.regioes.all())
    regioes = [regiao for regiao in todas if not eh_placeholder(regiao)]
    placeholders = len(todas) - len(regioes)
    campos = CampoExtraido.objects.filter(regiao__lote=lote, regiao__in=regioes)
    campos_uteis = campos.exclude(valor_original="").exclude(chave="titulo").exclude(chave="observacao")
    tipos = {}
    for regiao in regioes:
        tipos[regiao.tipo_documental] = tipos.get(regiao.tipo_documental, 0) + 1
    multiplas = sum(1 for pagina in paginas if pagina.quantidade_regioes > 1)
    com_candidato = sum(1 for pagina in paginas if pagina.tipos_candidatos)
    confirmadas = sum(
        1 for pagina in paginas if pagina.estado_classificacao in {EstadoClassificacao.CONFIRMADO, EstadoClassificacao.CORRIGIDO}
    )
    inconclusivas = sum(
        1
        for pagina in paginas
        if not pagina.tipos_candidatos or pagina.estado_classificacao == EstadoClassificacao.INCONCLUSIVO
    )
    revisadas = sum(1 for pagina in paginas if pagina.estado_revisao == EstadoRevisao.REVISADA)
    pendentes_revisao = sum(1 for pagina in paginas if pagina.estado_revisao == EstadoRevisao.PENDENTE)
    ilegiveis = sum(1 for pagina in paginas if pagina.estado_revisao == EstadoRevisao.ILEGIVEL or pagina.legibilidade == "ilegivel")
    por_tecnica = {}
    for pagina in paginas:
        chave = pagina.tecnica_utilizada or "indefinida"
        por_tecnica[chave] = por_tecnica.get(chave, 0) + 1
    return {
        "paginas_inventariadas": len(paginas),
        "paginas_com_candidato": com_candidato,
        "paginas_classificadas": com_candidato,
        "paginas_classificacao_confirmada": confirmadas,
        "paginas_inconclusivas": inconclusivas,
        "paginas_multiplas_pecas": multiplas,
        "paginas_revisadas": revisadas,
        "paginas_revisao_pendente": pendentes_revisao,
        "paginas_ilegiveis": ilegiveis,
        "tipos_encontrados": tipos,
        "pecas_identificadas": len(regioes),
        "pecas_efetivas": len(regioes),
        "pecas_placeholder": placeholders,
        "pecas_registros": len(todas),
        "pecas_total": len(todas),
        "pecas_confirmadas": sum(1 for r in regioes if r.estado_classificacao == EstadoClassificacao.CONFIRMADO),
        "pecas_sugeridas": sum(1 for r in regioes if r.estado_classificacao == EstadoClassificacao.PROPOSTO),
        "pecas_pendentes": sum(1 for r in regioes if r.estado_revisao == EstadoRevisao.PENDENTE),
        "campos_extraidos": campos_uteis.count(),
        "campos_confirmados": campos.filter(estado_revisao__in={EstadoCampo.CONFIRMADO, EstadoCampo.CORRIGIDO}).count(),
        "campos_revisados": campos.filter(estado_revisao__in={EstadoCampo.CONFIRMADO, EstadoCampo.CORRIGIDO}).count(),
        "ilegivel_ou_ambiguo": lote.pendencias.filter(status=StatusPendencia.ABERTA).count(),
        "pendencias_abertas": lote.pendencias.filter(status=StatusPendencia.ABERTA).count(),
        "cobertura_tecnica": por_tecnica,
        "duracao_ms": lote.duracao_processamento_ms,
        "limitacoes": lote.limitacoes,
        "processo_parcial": lote.numero_processo_parcial,
        "processo_parceria": lote.prestacao_parceria.numero_processo,
        "instrumento": lote.numero_instrumento,
        "hash_sha256": lote.hash_sha256,
        "nome_original": lote.documento.nome_original,
        "aviso_inventario": (
            "Registro de peça é toda região gravada. "
            "Peça efetiva exclui menção sem documento e página inteira inconclusiva. "
            "O inventário de páginas não equivale à classificação integral. "
            "O inventário não transforma inspeção complementar em classificação."
        ),
    }


VERSAO_EXTRACAO_REGIAO = "6.1.3"


def reprocessar_pagina_por_imagem(lote_id: int, numero: int, usuario=None) -> dict:
    """
    Recorta uma página pelas faixas em branco e extrai cada peça do seu OCR.
    Não reprocessa o lote nem altera o PDF original.
    """
    del usuario
    from pdf2image import convert_from_path

    from aplicacao.documentos.armazenamento import ler_arquivo
    from aplicacao.documentos.ocr import ServicoOCR
    from aplicacao.laboratorio.segmentacao import faixas_da_imagem

    lote = LoteLaboratorio.objects.select_related("documento").get(pk=lote_id)
    inventario = lote.paginas.get(numero_fisico=numero)
    hash_antes = lote.hash_sha256
    paginas_antes = lote.paginas.count()
    outras_antes = lote.regioes.exclude(pagina=inventario).count()
    caminho = ler_arquivo(lote.documento.nome_armazenado)
    imagens = convert_from_path(str(caminho), dpi=200, first_page=numero, last_page=numero)
    if not imagens:
        raise ErroLaboratorio("A página não gerou imagem para segmentação.")
    imagem = imagens[0]
    faixas = faixas_da_imagem(imagem)
    if not faixas:
        return _retorno_pagina(numero, 0, [], True, lote, hash_antes, paginas_antes, outras_antes)
    ocr = ServicoOCR()
    largura, altura = imagem.size
    pecas = []
    for ordem, faixa in enumerate(faixas, start=1):
        x0 = max(0, int(faixa["x"] * largura))
        y0 = max(0, int(faixa["y"] * altura))
        x1 = min(largura, int((faixa["x"] + faixa["largura"]) * largura))
        y1 = min(altura, int((faixa["y"] + faixa["altura"]) * altura))
        if x1 <= x0 or y1 <= y0:
            continue
        recorte = imagem.crop((x0, y0, x1, y1))
        texto, palavras = ocr.extrair_imagem_com_caixas(recorte)
        partes = [(recorte, texto, palavras, 0.0, 1.0, False, False)]
        corte_dispensa = dividir_dispensa_e_transferencia(texto, palavras)
        corte = corte_dispensa or dividir_transferencia_e_holerite(texto, palavras)
        if corte:
            altura_px = recorte.size[1]
            limite = max(1, min(altura_px - 1, int(corte * altura_px)))
            partes = []
            for imagem_parte, y_rel, alt_rel in (
                (recorte.crop((0, 0, recorte.size[0], limite)), 0.0, corte),
                (recorte.crop((0, limite, recorte.size[0], altura_px)), corte, 1 - corte),
            ):
                texto_parte, palavras_parte = ocr.extrair_imagem_com_caixas(imagem_parte)
                partes.append((imagem_parte, texto_parte, palavras_parte, y_rel, alt_rel, True, bool(corte_dispensa)))
        for recorte_parte, texto_parte, palavras_parte, y_rel, alt_rel, separada, separou_dispensa in partes:
            candidatos = candidatos_da_peca(
                [item for item in classificar_texto(texto_parte) if item["tipo"] != "outros_nao_classificados"],
                texto_parte,
            )
            if not candidatos:
                continue
            principal = tipo_principal(candidatos, texto_parte) or candidatos[0]
            tipos = [item["tipo"] for item in candidatos]
            texto_util = recortar_texto_para_tipo(texto_parte, principal["tipo"], tipos) if len(tipos) > 1 else texto_parte
            pecas.append(
                {
                    "ordem": len(pecas) + 1,
                    "tipo": principal["tipo"],
                    "confianca": principal["confianca"],
                    "texto": (texto_util or "")[:20000],
                    "mistura": len(tipos) > 1,
                    "x": faixa["x"],
                    "y": round(faixa["y"] + (y_rel * faixa["altura"]), 4),
                    "largura": faixa["largura"],
                    "altura": round(alt_rel * faixa["altura"], 4),
                    "ordem_visual": ordem,
                    "palavras": palavras_parte,
                    "recorte": recorte_parte,
                    "separada": separada,
                    "separou_dispensa": separou_dispensa,
                }
            )
    if not pecas:
        return _retorno_pagina(numero, len(faixas), [], True, lote, hash_antes, paginas_antes, outras_antes)
    from django.conf import settings

    idioma = settings.OCR_IDIOMA
    with transaction.atomic():
        inventario.regioes.all().delete()
        for peca in pecas:
            regiao = RegiaoDocumental.objects.create(
                lote=lote,
                pagina=inventario,
                tipo_documental=peca["tipo"],
                ordem=peca["ordem"],
                x=peca["x"],
                y=peca["y"],
                largura=peca["largura"],
                altura=peca["altura"],
                metodo_deteccao=(
                    "separacao_dispensa_transferencia"
                    if peca.get("separou_dispensa")
                    else "separacao_transferencia_holerite"
                    if peca.get("separada")
                    else "faixa_em_branco"
                ),
                confianca=peca["confianca"],
                versao_classificacao=1,
                versao_extracao=VERSAO_EXTRACAO_REGIAO,
                estado_classificacao=EstadoClassificacao.PROPOSTO,
                estado_revisao=EstadoRevisao.PENDENTE,
                texto_regiao=peca["texto"],
                justificativa=(
                    (
                        "Separação entre comunicação de dispensa e comprovante de transferência. Revisão humana pendente."
                        if peca.get("separou_dispensa")
                        else "Separação entre transferência e holerite pelo conteúdo visual. Revisão humana pendente."
                        if peca.get("separada")
                        else "Separação pela faixa em branco. Revisão humana pendente."
                    )
                    + (
                        " A região ainda contém mais de um tipo; a extração usou só o tipo predominante."
                        if peca["mistura"]
                        else ""
                    )
                ),
            )
            faixa = {"x": peca["x"], "y": peca["y"], "largura": peca["largura"], "altura": peca["altura"]}
            campos = extrair_campos(regiao.tipo_documental, peca["texto"], numero, "ocr_regiao")
            _reler_campos_dificeis(campos, peca["recorte"], peca["palavras"], peca["texto"], idioma)
            localizar_campos(campos, peca["palavras"], faixa)
            texto_tabela = ""
            palavras_rubrica = peca["palavras"]
            if regiao.tipo_documental == "termo_rescisao":
                texto_tabela, palavras_rubrica = _ler_tabela_verbas(ocr, peca["recorte"], peca["palavras"])
                if texto_tabela:
                    _aplicar_rubricas_na_verba(campos, peca["texto"], texto_tabela)
                _completar_liquido_lido(campos, peca["recorte"])
            if regiao.tipo_documental in {"termo_quitacao", "termo_rescisao"}:
                _completar_traco_quitacao(campos, imagem, peca["palavras"], faixa)
            if regiao.tipo_documental == "comunicacao_dispensa":
                _completar_data_comunicacao(campos, ocr, peca["recorte"], peca["palavras"], faixa)
            CampoExtraido.objects.bulk_create(
                [
                    CampoExtraido(
                        regiao=regiao,
                        esquema=campo["esquema"],
                        chave=campo["chave"],
                        rotulo=campo["rotulo"],
                        valor_original=campo["valor_original"],
                        valor_normalizado=campo["valor_normalizado"],
                        numero_pagina=numero,
                        trecho_evidencia=campo["trecho_evidencia"],
                        evidencia_x=campo.get("evidencia_x"),
                        evidencia_y=campo.get("evidencia_y"),
                        evidencia_largura=campo.get("evidencia_largura"),
                        evidencia_altura=campo.get("evidencia_altura"),
                        localizacao_precisa=bool(campo.get("localizacao_precisa")),
                        metodo=campo["metodo"],
                        estado_confianca=campo["estado_confianca"],
                        estado_revisao=(
                            EstadoCampo.AUSENTE
                            if not campo["valor_original"] and campo.get("estado_confianca") not in {"ambiguo", "inconsistente", "parcial"}
                            else EstadoCampo.PENDENTE
                        ),
                        obrigatorio=campo["obrigatorio"],
                    )
                    for campo in campos
                ]
            )
            _gravar_rubricas(regiao, peca["texto"], palavras_rubrica, faixa, texto_tabela)
        inventario.tipos_candidatos = [peca["tipo"] for peca in pecas]
        inventario.quantidade_regioes = len(pecas)
        inventario.estado_classificacao = EstadoClassificacao.PROPOSTO
        inventario.estado_revisao = EstadoRevisao.PENDENTE
        inventario.tecnica_utilizada = MetodoExtracao.OCR
        campos_pagina = ["tipos_candidatos", "quantidade_regioes", "estado_classificacao", "estado_revisao", "tecnica_utilizada"]
        if inventario.proveniencia == "ocr_recorte_rodape":
            inventario.numero_impresso = ""
            inventario.proveniencia = ""
            campos_pagina.extend(["numero_impresso", "proveniencia"])
        inventario.save(update_fields=campos_pagina)
        sugerir_vinculos(lote)
    lote.refresh_from_db()
    return _retorno_pagina(numero, len(faixas), pecas, False, lote, hash_antes, paginas_antes, outras_antes)


def _retorno_pagina(numero, faixas, pecas, mantida, lote, hash_antes, paginas_antes, outras_antes) -> dict:
    return {
        "pagina": numero,
        "faixas": faixas,
        "pecas": [
            {
                "tipo": peca["tipo"],
                "y": peca["y"],
                "altura": peca["altura"],
                "mistura": peca["mistura"],
                "caracteres": len(peca["texto"]),
            }
            for peca in pecas
        ],
        "mantida_segmentacao_anterior": mantida,
        "hash_preservado": lote.hash_sha256 == hash_antes,
        "paginas_antes": paginas_antes,
        "paginas_inventario": lote.paginas.count(),
        "regioes_outras_antes": outras_antes,
        "regioes_outras_depois": lote.regioes.exclude(pagina__numero_fisico=numero).count(),
    }


def _reler_campos_dificeis(campos: list[dict], recorte, palavras: list[dict], texto: str, idioma: str) -> None:
    import re

    faixa_auth = faixa_do_rotulo(palavras, r"autentic")
    if faixa_auth:
        original = next((campo["valor_original"] for campo in campos if campo["chave"] == "autenticacao"), "")
        aplicar_em_campos(campos, "autenticacao", decidir_autenticacao(original, reler_faixa(recorte, faixa_auth, idioma)))
    faixa_cadastro = faixa_abaixo(palavras, r"adastro")
    if faixa_cadastro:
        aplicar_em_campos(campos, "matricula", decidir_matricula(reler_faixa(recorte, faixa_cadastro, idioma)))
    faixa_recebi = faixa_do_rotulo(palavras, r"recebi", altura=0.06)
    if faixa_recebi is None and re.search(r"recebi", texto or "", flags=re.IGNORECASE):
        faixa_recebi = {"x": 0.0, "y": 0.86, "largura": 0.72, "altura": 0.12}
    if faixa_recebi:
        aplicar_em_campos(campos, "data_recebimento", decidir_data(reler_faixa(recorte, faixa_recebi, idioma)))


def _completar_liquido_lido(campos: list[dict], recorte) -> None:
    """Segunda leitura só da faixa inferior do TRCT. Não grava o valor calculado no campo lido."""
    import re

    import pytesseract
    from PIL import ImageOps

    from aplicacao.laboratorio.extracao import _moeda_para_decimal, liquido_lido_no_texto

    atual = next((campo for campo in campos if campo["chave"] == "total_liquido"), None)
    if atual is None or atual.get("valor_original"):
        return
    largura, altura = recorte.size
    if altura < 40:
        return
    inicio_rel = 0.8
    faixa = recorte.crop((0, int(altura * inicio_rel), largura, altura))
    preparada = ImageOps.autocontrast(faixa.convert("L"))
    try:
        texto = pytesseract.image_to_string(preparada, lang="por", config="--psm 4") or ""
    except Exception:
        return
    valor = liquido_lido_no_texto(texto)
    if not valor:
        return
    decimal = _moeda_para_decimal(valor)
    calculado = next((campo for campo in campos if campo["chave"] == "liquido_calculado"), None)
    decimal_calculado = _moeda_para_decimal((calculado or {}).get("valor_original") or "")
    atual["valor_original"] = valor
    atual["valor_normalizado"] = str(decimal) if decimal is not None else ""
    atual["trecho_evidencia"] = f"VALOR LÍQUIDO {valor}"
    atual["metodo"] = "ocr_recorte"
    atual["estado_confianca"] = (
        "ambiguo" if decimal is not None and decimal_calculado is not None and decimal != decimal_calculado else "parcial"
    )
    atual["localizacao_precisa"] = False
    try:
        dados = pytesseract.image_to_data(preparada, lang="por", config="--psm 4", output_type=pytesseract.Output.DICT)
    except Exception:
        return
    alvo = re.sub(r"\D", "", valor)
    posicoes = [indice for indice, token in enumerate(dados.get("text", [])) if re.sub(r"\D", "", str(token)) == alvo and alvo]
    if len(posicoes) != 1:
        return
    indice = posicoes[0]
    faixa_altura = max(preparada.size[1], 1)
    faixa_rel = 1 - inicio_rel
    atual.update(
        {
            "evidencia_x": round(int(dados["left"][indice]) / max(largura, 1), 4),
            "evidencia_y": round(inicio_rel + (int(dados["top"][indice]) / faixa_altura) * faixa_rel, 4),
            "evidencia_largura": round(max(int(dados["width"][indice]) / max(largura, 1), 0.02), 4),
            "evidencia_altura": round(max((int(dados["height"][indice]) / faixa_altura) * faixa_rel, 0.012), 4),
            "localizacao_precisa": True,
        }
    )


def _densidade_traco(imagem, y0: float, y1: float) -> float:
    cinza = imagem.convert("L")
    largura, altura = cinza.size
    superior = max(0, min(altura - 2, int(y0 * altura)))
    inferior = max(superior + 1, min(altura, int(y1 * altura)))
    faixa = cinza.crop((int(largura * 0.08), superior, int(largura * 0.92), inferior))
    largura_faixa, altura_faixa = faixa.size
    pixels = list(faixa.getdata())
    linhas = 0
    for linha in range(altura_faixa):
        inicio = linha * largura_faixa
        escuros = sum(1 for pixel in pixels[inicio : inicio + largura_faixa] if pixel < 160)
        proporcao = escuros / max(largura_faixa, 1)
        if 0.015 <= proporcao <= 0.45:
            linhas += 1
    return linhas / max(altura_faixa, 1)


def _completar_traco_quitacao(campos: list[dict], imagem, palavras: list[dict], faixa_peca: dict) -> None:
    """Nota presença visual ou pendência. Não usa o título e não afirma ausência nem autenticidade."""
    atual = next((campo for campo in campos if campo["chave"] == "assinaturas"), None)
    if atual is None or atual.get("valor_original"):
        return
    rotulos = [palavra for palavra in palavras if "assin" in (palavra.get("texto") or "").lower()]
    if rotulos:
        y_base = faixa_peca["y"] + min(float(palavra["y"]) for palavra in rotulos) * faixa_peca["altura"]
        y_fim = faixa_peca["y"] + max(float(palavra["y"]) for palavra in rotulos) * faixa_peca["altura"] + 0.12
    else:
        y_base = faixa_peca["y"] + faixa_peca["altura"] * 0.72
        y_fim = faixa_peca["y"] + faixa_peca["altura"] + 0.08
    y_fim = min(0.92, y_fim)
    densidade = 0.0
    cursor = y_base
    while cursor < y_fim - 0.04:
        densidade = _densidade_traco(imagem, cursor, min(y_fim, cursor + 0.08))
        if 0.04 <= densidade <= 0.25:
            break
        cursor += 0.03
    if 0.04 <= densidade <= 0.25:
        atual["valor_original"] = (
            "Traço manuscrito visível. Signatário não identificado. "
            "A presença não comprova autenticidade nem quitação."
        )
        atual["trecho_evidencia"] = "Faixa do termo abaixo do rótulo de assinatura."
        atual["localizacao_precisa"] = True
        atual["evidencia_x"] = 0.08
        atual["evidencia_y"] = round(cursor, 4)
        atual["evidencia_largura"] = 0.84
        atual["evidencia_altura"] = 0.08
    else:
        atual["valor_original"] = (
            "Conferência visual pendente. A leitura automática não confirma nem nega assinatura."
        )
        atual["trecho_evidencia"] = "A faixa observada não permitiu decidir a presença do traço."
    atual["valor_normalizado"] = atual["valor_original"]
    atual["metodo"] = "imagem_regiao"
    atual["estado_confianca"] = "parcial"


def _ler_tabela_verbas(ocr, recorte, palavras: list[dict]) -> tuple[str, list[dict]]:
    """Relê cada linha de rubrica ampliada. O contraste da página inteira confunde dígitos."""
    import re

    candidatos = []
    for palavra in palavras:
        texto = (palavra.get("texto") or "").strip()
        if not re.fullmatch(r"\d{2,3}(?:\.\d)?", texto):
            continue
        base = int(texto.split(".")[0])
        if 50 <= base <= 199:
            candidatos.append(float(palavra["y"]))
    linhas_y = []
    for y in sorted(candidatos):
        if linhas_y and abs(y - linhas_y[-1]) <= 0.016:
            continue
        linhas_y.append(y)
    if len(linhas_y) < 2:
        return "", palavras
    altura_px = recorte.size[1]
    textos = []
    projetadas = []
    for y in linhas_y:
        y0 = max(0.0, y - 0.012)
        y1 = min(1.0, y + 0.022)
        if y1 <= y0:
            continue
        tabela = recorte.crop((0, int(y0 * altura_px), recorte.size[0], max(int(y1 * altura_px), int(y0 * altura_px) + 8)))
        try:
            texto, palavras_tabela = ocr.extrair_linha_ampliada(tabela)
        except RuntimeError:
            continue
        if texto:
            textos.append(texto)
        for palavra in palavras_tabela:
            copia = dict(palavra)
            copia["y"] = y0 + float(palavra["y"]) * (y1 - y0)
            copia["altura"] = float(palavra["altura"]) * (y1 - y0)
            projetadas.append(copia)
    unicas = []
    for copia in projetadas:
        repetida = any(
            copia.get("texto") == outra.get("texto")
            and abs(float(copia["x"]) - float(outra["x"])) < 0.02
            and abs(float(copia["y"]) - float(outra["y"])) < 0.015
            for outra in unicas
        )
        if not repetida:
            unicas.append(copia)
    return normalizar_pontuacao_monetaria("\n".join(textos)), unicas or palavras


def _completar_data_comunicacao(campos: list[dict], ocr, recorte, palavras: list[dict], faixa: dict) -> None:
    """Segunda leitura do rótulo Local e data. Não copia data de outro documento."""
    from aplicacao.laboratorio.extracao import _data_da_comunicacao
    from aplicacao.laboratorio.localizacao import caixa_do_valor, projetar_pagina

    atual = next((campo for campo in campos if campo["chave"] == "data_comunicacao"), None)
    if atual is None or atual.get("valor_original"):
        return
    altura = recorte.size[1]
    inicio = int(altura * 0.5)
    if altura - inicio < 24:
        return
    try:
        texto, palavras_linha = ocr.extrair_linha_ampliada(recorte.crop((0, inicio, recorte.size[0], altura)))
    except RuntimeError:
        return
    data, confianca, evidencia, metodo = _data_da_comunicacao(texto or "")
    if not data and confianca != "parcial":
        return
    if data:
        atual["valor_original"] = data
        atual["valor_normalizado"] = data
        atual["estado_confianca"] = "parcial"
        atual["metodo"] = "ocr_linha"
    else:
        atual["valor_original"] = ""
        atual["valor_normalizado"] = ""
        atual["estado_confianca"] = "parcial"
        atual["metodo"] = metodo or "validacao_semantica"
    if evidencia:
        anterior = atual.get("trecho_evidencia") or ""
        if "rejeitado" in anterior.lower() and "rejeitado" not in evidencia.lower():
            atual["trecho_evidencia"] = f"{evidencia} {anterior}"[:500]
        else:
            atual["trecho_evidencia"] = evidencia
    projetadas = []
    for palavra in palavras_linha:
        copia = dict(palavra)
        copia["y"] = 0.5 + float(palavra["y"]) * 0.5
        projetadas.append(copia)
    caixa = caixa_do_valor(projetadas, "LOCAL E DATA") or caixa_do_valor(palavras, "LOCAL E DATA")
    if caixa:
        atual.update(projetar_pagina(caixa, faixa))
        atual["localizacao_precisa"] = True


def _aplicar_rubricas_na_verba(campos: list[dict], texto_pagina: str, texto_tabela: str) -> None:
    itens = mesclar_rubricas_rescisao(texto_pagina, texto_tabela)
    linhas = []
    for item in itens:
        valor = item["valor_original"] or "valor não lido"
        linhas.append(f"{item['codigo']} {item['descricao']} {valor}")
    verba = next((campo for campo in campos if campo["chave"] == "verbas_rescisorias"), None)
    if verba is not None and linhas:
        verba["valor_original"] = "\n".join(linhas)[:800]
        verba["valor_normalizado"] = verba["valor_original"]
        verba["trecho_evidencia"] = (
            "Leitura estruturada da tabela. O OCR integral permanece no texto da região.\n" + verba["valor_original"]
        )[:900]
        verba["metodo"] = "ocr_tabela"
        verba["estado_confianca"] = "parcial"


def _gravar_rubricas(regiao, texto: str, palavras: list[dict], faixa: dict, texto_tabela: str = "") -> None:
    linhas = []
    if regiao.tipo_documental == "termo_rescisao":
        fonte = mesclar_rubricas_rescisao(texto, texto_tabela) if texto_tabela else estruturar_rubricas_rescisao(texto)
    else:
        fonte = estruturar_rubricas(texto)
    for ordem, item in enumerate(fonte, start=1):
        if regiao.tipo_documental == "termo_rescisao":
            caixa = caixa_da_rubrica(palavras, item["codigo"], item["valor_original"])
        else:
            caixa = caixa_do_valor(palavras, item["trecho_evidencia"]) or caixa_do_valor(palavras, item["valor_original"])
        coords = projetar_pagina(caixa, faixa) if caixa else {}
        linhas.append(
            RubricaExtraida(
                regiao=regiao,
                ordem=ordem,
                localizacao_precisa=bool(caixa),
                evidencia_x=coords.get("evidencia_x"),
                evidencia_y=coords.get("evidencia_y"),
                evidencia_largura=coords.get("evidencia_largura"),
                evidencia_altura=coords.get("evidencia_altura"),
                **item,
            )
        )
    if linhas:
        RubricaExtraida.objects.bulk_create(linhas)
