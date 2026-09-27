"""FinOps lê preços cadastrados. Não consulta a internet e não inventa valor."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from aplicacao.inteligencia_artificial.models import LimiteConsumoInteligenciaArtificial, ModeloInteligenciaArtificial
from aplicacao.painel.consultas.filtros import FiltrosPainel
from aplicacao.painel.consultas.recortes import meses, somar, usos
from aplicacao.painel.consultas.tipos import NAO_DISPONIVEL, SEM_HISTORICO, Indicador, Linha, PainelAba, Serie, grafico, texto_contagem, texto_decimal

SEIS = Decimal("0.000001")


def _dia(momento):
    if momento is None:
        return None
    if timezone.is_aware(momento):
        return timezone.localtime(momento).date()
    return momento.date()


def _precos(modelo_ids: set[int]) -> dict:
    from aplicacao.inteligencia_artificial.models import PrecoModeloInteligenciaArtificial

    mapa: dict[int, list] = {}
    for preco in PrecoModeloInteligenciaArtificial.objects.filter(modelo_id__in=modelo_ids):
        mapa.setdefault(preco.modelo_id, []).append(preco)
    return mapa


def custo_da_chamada(uso, mapa) -> Decimal | None:
    if not uso.modelo_id:
        return None
    dia = _dia(uso.iniciada_em)
    if dia is None:
        return None
    candidatos = [
        preco
        for preco in mapa.get(uso.modelo_id, [])
        if preco.vigencia_inicio <= dia and (preco.vigencia_fim is None or preco.vigencia_fim >= dia)
    ]
    if not candidatos:
        return None
    preco = max(candidatos, key=lambda item: item.vigencia_inicio)
    unidade = Decimal(preco.unidade_precificacao)
    if unidade == 0:
        return None
    entrada = (Decimal(uso.tokens_entrada) / unidade * preco.preco_entrada).quantize(SEIS)
    saida = (Decimal(uso.tokens_saida) / unidade * preco.preco_saida).quantize(SEIS)
    return (entrada + saida).quantize(SEIS)


def _acumular(qs):
    identificadores = set(qs.exclude(modelo_id__isnull=True).values_list("modelo_id", flat=True))
    mapa = _precos(identificadores)
    total = None
    sem_preco = 0
    por_provedor: dict[str, Decimal | None] = {}
    por_modelo: dict[str, Decimal | None] = {}
    por_agente: dict[str, Decimal | None] = {}
    por_prestacao: dict[str, Decimal | None] = {}
    sem_por = {"provedor": {}, "modelo": {}, "agente": {}, "prestacao": {}}
    for uso in qs.iterator():
        custo = custo_da_chamada(uso, mapa)
        chave_modelo = uso.identificador_modelo or str(uso.modelo_id or "sem modelo")
        chave_prestacao = str(uso.prestacao_contas_id or "sem prestação")
        if custo is None:
            sem_preco += 1
            sem_por["provedor"][uso.provedor] = sem_por["provedor"].get(uso.provedor, 0) + 1
            sem_por["modelo"][chave_modelo] = sem_por["modelo"].get(chave_modelo, 0) + 1
            sem_por["agente"][uso.agente] = sem_por["agente"].get(uso.agente, 0) + 1
            sem_por["prestacao"][chave_prestacao] = sem_por["prestacao"].get(chave_prestacao, 0) + 1
            continue
        total = custo if total is None else total + custo
        for destino, chave in (
            (por_provedor, uso.provedor or "Não informado"),
            (por_modelo, chave_modelo),
            (por_agente, uso.agente or "Não informado"),
            (por_prestacao, chave_prestacao),
        ):
            destino[chave] = custo if destino.get(chave) is None else destino[chave] + custo
    return {
        "total": total,
        "sem_preco": sem_preco,
        "por_provedor": por_provedor,
        "por_modelo": por_modelo,
        "por_agente": por_agente,
        "por_prestacao": por_prestacao,
    }


def _series_custo(mapa: dict) -> list[Serie]:
    series = []
    for chave, valor in mapa.items():
        if valor is None:
            continue
        escala = int((valor * Decimal("1000000")).to_integral_value())
        series.append(Serie(chave, max(escala, 1), texto_decimal(valor, SEIS)))
    return series


def montar_finops(filtros: FiltrosPainel) -> PainelAba:
    qs = usos(filtros)
    existe = qs.exists()
    resumo = _acumular(qs) if existe else {"total": None, "sem_preco": 0, "por_provedor": {}, "por_modelo": {}, "por_agente": {}, "por_prestacao": {}}
    tokens_entrada = somar(qs, "tokens_entrada") if existe else None
    tokens_saida = somar(qs, "tokens_saida") if existe else None
    tokens_total = somar(qs, "tokens_total") if existe else None
    limites = LimiteConsumoInteligenciaArtificial.objects.filter(ativo=True)
    pontos = meses(qs, "iniciada_em") if existe else []
    historico = None
    mensagem = SEM_HISTORICO
    if len(pontos) >= 2:
        historico = grafico(
            "Histórico de chamadas",
            "Chamadas por mês. Custo não é estimado para meses sem preço.",
            [Serie(f"{mes:%Y-%m}", quantidade, texto_contagem(quantidade)) for mes, quantidade in pontos],
            SEM_HISTORICO,
        )
        mensagem = ""
    observacao_custo = "Soma das chamadas com preço vigente na data da chamada. Chamadas sem preço não viram zero."
    if resumo["sem_preco"]:
        observacao_custo += f" {resumo['sem_preco']} chamada(s) sem preço vigente."
    return PainelAba(
        kpis=[
            Indicador("Chamadas", texto_contagem(qs.count()) if existe else NAO_DISPONIVEL),
            Indicador("Tokens de entrada", texto_contagem(int(tokens_entrada)) if tokens_entrada is not None else NAO_DISPONIVEL),
            Indicador("Tokens de saída", texto_contagem(int(tokens_saida)) if tokens_saida is not None else NAO_DISPONIVEL),
            Indicador("Tokens totais", texto_contagem(int(tokens_total)) if tokens_total is not None else NAO_DISPONIVEL),
            Indicador("Custo total", texto_decimal(resumo["total"], SEIS), observacao=observacao_custo),
            Indicador("Chamadas sem preço vigente", texto_contagem(resumo["sem_preco"]) if existe else NAO_DISPONIVEL, observacao="Custo não disponível: não há preço vigente cadastrado para o modelo na data da chamada."),
            Indicador("Modelos", texto_contagem(ModeloInteligenciaArtificial.objects.count())),
            Indicador("Limites ativos", texto_contagem(limites.count())),
            Indicador("Chamadas com limite excedido", texto_contagem(qs.filter(status="limite_excedido").count()) if existe else NAO_DISPONIVEL),
        ],
        graficos=[
            grafico("Custo por provedor", observacao_custo, _series_custo(resumo["por_provedor"]), "Custo não disponível: não há preço vigente cadastrado para o modelo."),
            grafico("Custo por modelo", observacao_custo, _series_custo(resumo["por_modelo"]), "Custo não disponível: não há preço vigente cadastrado para o modelo."),
            grafico("Custo por agente", observacao_custo, _series_custo(resumo["por_agente"]), "Custo não disponível: não há preço vigente cadastrado para o modelo."),
            grafico("Custo por prestação", "Prestação vinculada à chamada, quando existir.", _series_custo(resumo["por_prestacao"]), "Sem custo relacionável a uma prestação."),
        ],
        historico=historico,
        mensagem_historico=mensagem,
        colunas=["Escopo", "Provedor", "Máximo de tentativas", "Máximo de caracteres"],
        linhas=[
            Linha([item.get_escopo_display(), item.provedor or "Qualquer", texto_contagem(item.max_tentativas), texto_contagem(item.max_caracteres_contexto)])
            for item in limites
        ],
        vazio_tabela="Sem limite de consumo ativo.",
        avisos=["O preço vem de PrecoModeloInteligenciaArtificial. Não há preço embutido no código nem consulta externa."] + _qualidade(qs),
    )


def _qualidade(qs) -> list[str]:
    from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial

    prestacoes = set(qs.exclude(prestacao_contas_id__isnull=True).values_list("prestacao_contas_id", flat=True))
    if not prestacoes:
        return []
    relacionaveis = AvaliacaoInteligenciaArtificial.objects.filter(prestacao_contas_id__in=prestacoes).exclude(metricas={}).count()
    if not relacionaveis:
        return ["Não há avaliação com métricas na mesma prestação das chamadas. Custo e qualidade não foram relacionados."]
    return [f"{relacionaveis} avaliação(ões) compartilham prestação com chamadas de IA. A coincidência não indica causa entre custo e qualidade."]
