from decimal import Decimal, ROUND_HALF_UP

from aplicacao.avaliacao.escolhas import ClassificacaoCorrespondencia

QUATRO = Decimal("0.0001")
CENTAVO = Decimal("0.01")


def _dividir(numerador: int, denominador: int) -> Decimal | None:
    if denominador == 0:
        return None
    return (Decimal(numerador) / Decimal(denominador)).quantize(QUATRO, rounding=ROUND_HALF_UP)


def calcular_classificacao(*, tp: int, fp: int, fn: int) -> dict:
    precisao = _dividir(tp, tp + fp)
    recall = _dividir(tp, tp + fn)
    if precisao is None or recall is None or (precisao + recall) == 0:
        f1 = None
    else:
        f1 = (2 * precisao * recall / (precisao + recall)).quantize(QUATRO, rounding=ROUND_HALF_UP)
    return {"tp": tp, "fp": fp, "fn": fn, "precisao": precisao, "recall": recall, "f1": f1}


def contar_correspondencias(correspondencias) -> dict:
    tp = fp = fn = parciais = pendentes = 0
    for item in correspondencias:
        if item.classificacao == ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO:
            tp += 1
        elif item.classificacao == ClassificacaoCorrespondencia.FALSO_POSITIVO:
            fp += 1
        elif item.classificacao == ClassificacaoCorrespondencia.FALSO_NEGATIVO:
            fn += 1
        elif item.classificacao == ClassificacaoCorrespondencia.CORRESPONDENCIA_PARCIAL:
            parciais += 1
        elif item.classificacao == ClassificacaoCorrespondencia.PENDENTE_REVISAO:
            pendentes += 1
    resultado = calcular_classificacao(tp=tp, fp=fp, fn=fn)
    resultado["parciais"] = parciais
    resultado["pendentes"] = pendentes
    return resultado


def materialidade_falsos_negativos(correspondencias) -> dict:
    valores = []
    quantidade = 0
    for item in correspondencias:
        if item.classificacao != ClassificacaoCorrespondencia.FALSO_NEGATIVO or item.ground_truth_achado_id is None:
            continue
        quantidade += 1
        valor = item.ground_truth_achado.materialidade
        if valor is not None:
            valores.append(Decimal(valor))
    if not valores:
        return {"quantidade": quantidade, "total": None, "media": None, "maior": None}
    total = sum(valores, Decimal("0.00")).quantize(CENTAVO)
    media = (total / Decimal(len(valores))).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return {"quantidade": quantidade, "total": total, "media": media, "maior": max(valores).quantize(CENTAVO)}


def texto_metrica(valor) -> str:
    if valor is None:
        return "Não disponível"
    if isinstance(valor, Decimal):
        return format(valor, "f").replace(".", ",")
    return str(valor).replace(".", ",")


def serializar(valor):
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, dict):
        return {chave: serializar(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [serializar(item) for item in valor]
    return valor
