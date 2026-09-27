"""ACH-001 e ACH-002 sobre os objetos concretos, sem reescrever a execução histórica."""


def avaliar_rastreabilidade(achado) -> bool:
    tem_fato = bool((achado.descricao_factual or "").strip())
    tem_regra = achado.vinculos_regra.filter(execucao__isnull=False).exists()
    tem_evidencia = achado.vinculos_evidencia.exists()
    return bool(tem_fato and tem_regra and tem_evidencia)


def avaliar_fundamentacao(achado) -> bool:
    if not achado.vinculos_regra.exists():
        return False
    fundamentos = list(achado.fundamentacoes.all())
    if not fundamentos:
        return False
    return all(item.trecho_normativo_id and item.norma_id and item.origem_resolucao == "resolvedor_normativo" for item in fundamentos)


def registrar_avaliacao_nas_execucoes(analise) -> None:
    from aplicacao.achados.models import Achado

    achados = list(Achado.objects.filter(analise=analise).values("codigo", "elementos_rastreaveis", "fundamentacao_suficiente"))
    for codigo in ("ACH-001", "ACH-002"):
        execucao = analise.execucoes.filter(regra__codigo=codigo).first()
        if execucao is None:
            continue
        entradas = dict(execucao.entradas or {})
        entradas["objetos_achado"] = achados
        execucao.entradas = entradas
        execucao.save(update_fields=["entradas"])
