import hashlib
import json


def conteudo_canonico(pre) -> dict:
    from aplicacao.pareceres.models import AfirmacaoPreAnalise

    afirmacoes = []
    for afirmacao in (
        AfirmacaoPreAnalise.objects.filter(secao__pre_analise=pre, exibir_oficial=True)
        .select_related("secao")
        .order_by("secao__ordem", "ordem", "id")
    ):
        afirmacoes.append(
            {
                "secao": afirmacao.secao.tipo,
                "ordem": afirmacao.ordem,
                "tipo": afirmacao.tipo,
                "texto": afirmacao.texto_atual,
                "fontes": list(afirmacao.fontes.order_by("codigo_fonte", "id").values_list("codigo_fonte", flat=True)),
            }
        )
    return {
        "codigo": pre.codigo,
        "versao": pre.versao,
        "resumo": pre.resumo_executivo,
        "encaminhamento": pre.encaminhamento,
        "afirmacoes": afirmacoes,
    }


def calcular_hash(pre) -> str:
    bruto = json.dumps(conteudo_canonico(pre), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()
