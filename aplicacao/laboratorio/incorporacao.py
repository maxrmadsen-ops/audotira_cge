"""Incorpora a amostra do Ciclo 6.1.5-B sem reprocessar páginas preservadas."""

from __future__ import annotations

from aplicacao.laboratorio.conciliacao import _cadeias_darf, _cadeias_folha
from aplicacao.laboratorio.escolhas import EstadoCampo, EstadoClassificacao, EstadoRevisao, EstadoVinculo
from aplicacao.laboratorio.extracao import extrair_campos
from aplicacao.laboratorio.models import CadeiaConciliacao, CampoExtraido, RegiaoDocumental
from aplicacao.laboratorio.servico import reprocessar_pagina_por_imagem

PAGINAS_AMOSTRA = (16, 18, 50, 110, 112, 115, 117)
PAGINAS_PRESERVADAS = frozenset({17, 91, 92, 93, 111, 116})
VERSAO_AMOSTRA = "6.1.5-b"


class ErroIncorporacao(Exception):
    """A página pedida sai da amostra controlada."""


def incorporar_amostra(lote, numeros=PAGINAS_AMOSTRA) -> list[dict]:
    pedidos = tuple(numeros)
    bloqueadas = sorted(set(pedidos) & PAGINAS_PRESERVADAS)
    if bloqueadas:
        raise ErroIncorporacao(f"Páginas preservadas fora da amostra: {bloqueadas}.")
    fora = sorted(numero for numero in pedidos if numero not in PAGINAS_AMOSTRA)
    if fora:
        raise ErroIncorporacao(f"Páginas fora da amostra controlada: {fora}.")
    relatorio = []
    for numero in pedidos:
        pagina = lote.paginas.select_related("pagina_documento").get(numero_fisico=numero)
        if pagina.regioes.filter(versao_extracao=VERSAO_AMOSTRA).exists():
            relatorio.append({"pagina": numero, "situacao": "ja_incorporada", "pecas": pagina.regioes.count()})
            continue
        if pagina.regioes.exists():
            raise ErroIncorporacao(f"A página {numero} já tem peças de outra versão.")
        reprocessar_pagina_por_imagem(lote.pk, numero)
        pagina.refresh_from_db()
        for regiao in pagina.regioes.all():
            _corrigir_tipo(regiao)
        _unir_fragmentos(pagina)
        pagina.regioes.update(versao_extracao=VERSAO_AMOSTRA)
        pagina.estado_classificacao = EstadoClassificacao.PROPOSTO
        pagina.estado_revisao = EstadoRevisao.PENDENTE
        pagina.quantidade_regioes = pagina.regioes.count()
        pagina.tipos_candidatos = [regiao.tipo_documental for regiao in pagina.regioes.order_by("ordem", "id")]
        pagina.save(
            update_fields=["estado_classificacao", "estado_revisao", "quantidade_regioes", "tipos_candidatos"]
        )
        relatorio.append(
            {
                "pagina": numero,
                "situacao": "incorporada",
                "pecas": [
                    {"id": regiao.pk, "tipo": regiao.tipo_documental, "ordem": regiao.ordem}
                    for regiao in pagina.regioes.order_by("ordem", "id")
                ],
            }
        )
    relatorio.append({"cadeias": _gravar_cadeias_novas(lote)})
    return relatorio


def _corrigir_tipo(regiao: RegiaoDocumental) -> None:
    baixo = (regiao.texto_regiao or "").lower()
    if "comprovante de pagamento de darf" in baixo or "darf/darf" in baixo or "convenio rfb-darf" in baixo:
        novo = "comprovante_darf"
    elif "documento de arrecada" in baixo or "receitas federais" in baixo:
        novo = "darf"
    else:
        return
    if regiao.tipo_documental == novo:
        return
    regiao.tipo_documental = novo
    regiao.estado_classificacao = EstadoClassificacao.PROPOSTO
    regiao.estado_revisao = EstadoRevisao.PENDENTE
    regiao.justificativa = "Classificação sugerida pela leitura do DARF. Revisão humana pendente."
    regiao.save(update_fields=["tipo_documental", "estado_classificacao", "estado_revisao", "justificativa", "atualizado_em"])
    _reextrair(regiao)


def _unir_fragmentos(pagina) -> None:
    for tipo in ("darf", "comprovante_darf"):
        grupo = list(pagina.regioes.filter(tipo_documental=tipo).order_by("y", "ordem"))
        if len(grupo) < 2:
            continue
        principal = max(grupo, key=lambda regiao: len(regiao.texto_regiao or ""))
        principal.texto_regiao = "\n".join(regiao.texto_regiao or "" for regiao in grupo)[:20000]
        principal.y = min(regiao.y for regiao in grupo)
        base = min(regiao.y for regiao in grupo)
        topo = max(regiao.y + regiao.altura for regiao in grupo)
        principal.altura = round(topo - base, 4)
        principal.justificativa = (
            "Fragmentos do mesmo documento foram reunidos para não duplicar o valor. Revisão humana pendente."
        )
        principal.save(update_fields=["texto_regiao", "y", "altura", "justificativa", "atualizado_em"])
        _reextrair(principal)
        for regiao in grupo:
            if regiao.pk != principal.pk:
                regiao.delete()


def _reextrair(regiao: RegiaoDocumental) -> None:
    regiao.campos.all().delete()
    campos = extrair_campos(regiao.tipo_documental, regiao.texto_regiao or "", regiao.pagina.numero_fisico, "ocr_regiao")
    CampoExtraido.objects.bulk_create(
        [
            CampoExtraido(
                regiao=regiao,
                esquema=campo["esquema"],
                chave=campo["chave"],
                rotulo=campo["rotulo"],
                valor_original=campo["valor_original"],
                valor_normalizado=campo["valor_normalizado"],
                numero_pagina=regiao.pagina.numero_fisico,
                trecho_evidencia=campo["trecho_evidencia"],
                metodo=campo["metodo"],
                estado_confianca=campo["estado_confianca"],
                estado_revisao=EstadoCampo.AUSENTE if not campo["valor_original"] else EstadoCampo.PENDENTE,
                obrigatorio=campo["obrigatorio"],
            )
            for campo in campos
        ]
    )


def _gravar_cadeias_novas(lote) -> list[str]:
    regioes = list(lote.regioes.select_related("pagina").prefetch_related("campos", "rubricas"))
    existentes = set(lote.cadeias.values_list("codigo", flat=True))
    criadas = []
    for proposta in _cadeias_folha(lote, regioes) + _cadeias_darf(lote, regioes):
        if proposta["codigo"] in existentes:
            continue
        if proposta["execucao"].pagina.numero_fisico not in PAGINAS_AMOSTRA:
            continue
        cadeia = CadeiaConciliacao(lote=lote, estado=EstadoVinculo.SUGERIDO)
        for campo, valor in proposta.items():
            setattr(cadeia, campo, valor)
        cadeia.save()
        criadas.append(cadeia.codigo)
    return criadas
