from aplicacao.avaliacao.escolhas import ClassificacaoCorrespondencia, MetodoCorrespondencia
from aplicacao.avaliacao.models import CorrespondenciaAchado

LIMIAR_POSITIVO = 7
LIMIAR_PARCIAL = 4


def _ids(manager, campo="id"):
    return set(manager.values_list(campo, flat=True))


def pontuar(achado, referencia) -> int:
    """Sinais estruturados. O texto do título não entra na pontuação."""

    pontos = 0
    regras_achado = _ids(achado.vinculos_regra, "regra_id")
    if regras_achado & _ids(referencia.regras):
        pontos += 4
    if achado.categoria and referencia.categoria and achado.categoria.casefold() == referencia.categoria.casefold():
        pontos += 2
    if (
        achado.materialidade_financeira is not None
        and referencia.materialidade is not None
        and achado.materialidade_financeira == referencia.materialidade
    ):
        pontos += 2
    evidencias_achado = _ids(achado.vinculos_evidencia, "evidencia_id")
    if evidencias_achado & _ids(referencia.evidencias):
        pontos += 3
    from aplicacao.achados.models import Evidencia

    documentos_achado = set(
        Evidencia.objects.filter(pk__in=evidencias_achado).exclude(documento_id=None).values_list("documento_id", flat=True)
    )
    documentos_referencia = _ids(referencia.documentos)
    documentos_referencia |= set(
        referencia.evidencias.exclude(documento_id=None).values_list("documento_id", flat=True)
    )
    if documentos_achado & documentos_referencia:
        pontos += 2
    if _ids(achado.pessoas) & _ids(referencia.pessoas):
        pontos += 2
    if _ids(achado.despesas) & _ids(referencia.despesas):
        pontos += 2
    if _ids(achado.pagamentos) & _ids(referencia.pagamentos):
        pontos += 2
    normas_achado = _ids(achado.fundamentacoes, "norma_id")
    if normas_achado & _ids(referencia.normas):
        pontos += 3
    return pontos


def comparar_achados(avaliacao, achados, referencias) -> list[CorrespondenciaAchado]:
    pares = []
    for referencia in referencias:
        for achado in achados:
            pontos = pontuar(achado, referencia)
            if pontos > 0:
                pares.append((pontos, achado, referencia))
    usados_achados = set()
    usados_referencias = set()
    pares_usados = set()
    criadas = []

    def registrar(achado, referencia, classificacao, pontos, revisao):
        chave = (getattr(achado, "pk", None), getattr(referencia, "pk", None))
        if chave in pares_usados:
            return
        pares_usados.add(chave)
        criadas.append(
            CorrespondenciaAchado.objects.create(
                avaliacao=avaliacao,
                achado=achado,
                ground_truth_achado=referencia,
                classificacao=classificacao,
                metodo=MetodoCorrespondencia.DETERMINISTICO,
                justificativa=f"Pontuação estruturada {pontos}. O texto não decidiu a correspondência.",
                revisao_humana_necessaria=revisao,
            )
        )
        if achado is not None:
            usados_achados.add(achado.pk)
        if referencia is not None:
            usados_referencias.add(referencia.pk)

    for referencia in referencias:
        candidatos = sorted((item for item in pares if item[2].pk == referencia.pk and item[0] >= LIMIAR_POSITIVO), key=lambda item: -item[0])
        if not candidatos:
            continue
        melhor = candidatos[0][0]
        fortes = [item for item in candidatos if item[0] >= melhor - 1]
        if len(fortes) == 1:
            achado = fortes[0][1]
            outros = [item for item in pares if item[1].pk == achado.pk and item[2].pk != referencia.pk and item[0] >= melhor - 1]
            if outros:
                for _, achado_item, referencia_item in fortes:
                    registrar(achado_item, referencia_item, ClassificacaoCorrespondencia.PENDENTE_REVISAO, fortes[0][0], True)
            else:
                registrar(achado, referencia, ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO, melhor, False)
        else:
            for pontos, achado, referencia_item in fortes:
                registrar(achado, referencia_item, ClassificacaoCorrespondencia.PENDENTE_REVISAO, pontos, True)

    for pontos, achado, referencia in pares:
        if pontos < LIMIAR_PARCIAL or pontos >= LIMIAR_POSITIVO:
            continue
        if achado.pk in usados_achados or referencia.pk in usados_referencias:
            continue
        registrar(achado, referencia, ClassificacaoCorrespondencia.CORRESPONDENCIA_PARCIAL, pontos, True)

    for referencia in referencias:
        if referencia.pk not in usados_referencias:
            criadas.append(
                CorrespondenciaAchado.objects.create(
                    avaliacao=avaliacao,
                    ground_truth_achado=referencia,
                    classificacao=ClassificacaoCorrespondencia.FALSO_NEGATIVO,
                    metodo=MetodoCorrespondencia.DETERMINISTICO,
                    justificativa="Nenhuma correspondência estruturada suficiente na análise congelada.",
                )
            )
    for achado in achados:
        if achado.pk not in usados_achados:
            criadas.append(
                CorrespondenciaAchado.objects.create(
                    avaliacao=avaliacao,
                    achado=achado,
                    classificacao=ClassificacaoCorrespondencia.FALSO_POSITIVO,
                    metodo=MetodoCorrespondencia.DETERMINISTICO,
                    justificativa="Achado da análise sem referência correspondente no Ground Truth.",
                )
            )
    return criadas


def registrar_sugestao_semantica(correspondencia, gerenciador) -> CorrespondenciaAchado:
    """A sugestão não promove correspondência ambígua a verdadeiro positivo."""

    if gerenciador is None or correspondencia.classificacao != ClassificacaoCorrespondencia.PENDENTE_REVISAO:
        return correspondencia
    gerenciador.executar(
        agente="auxiliar_matching_avaliacao",
        entrada={"correspondencia": correspondencia.pk, "instrucao": "Sugira apenas. Não decida."},
        schema={"type": "object"},
    )
    correspondencia.metodo = MetodoCorrespondencia.SUGESTAO_SEMANTICA
    correspondencia.classificacao = ClassificacaoCorrespondencia.PENDENTE_REVISAO
    correspondencia.revisao_humana_necessaria = True
    correspondencia.confianca = None
    correspondencia.justificativa = (correspondencia.justificativa + "\nSugestão semântica registrada. Não decide a correspondência.").strip()
    correspondencia.save(update_fields=["metodo", "classificacao", "revisao_humana_necessaria", "confianca", "justificativa"])
    return correspondencia
