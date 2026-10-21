"""Segmentação por faixa em branco. Não divide a página em metades iguais."""

from __future__ import annotations


def faixas_por_densidade(
    densidades: list[float],
    limiar: float = 0.004,
    intervalo_linha: float = 0.012,
    intervalo_documento: float = 0.032,
    altura_minima: float = 0.08,
) -> list[dict]:
    """
    Agrupa linhas com tinta e separa peças quando a faixa em branco é maior
    que o espaçamento interno de um formulário.
    Coordenadas y/altura ficam normalizadas entre 0 e 1.
    """
    total = len(densidades)
    if total == 0:
        return []
    ponte = max(1, int(round(total * intervalo_linha)))
    conteudo = [False] * total
    for indice, densidade in enumerate(densidades):
        if densidade < limiar:
            continue
        inicio = max(0, indice - ponte)
        fim = min(total, indice + ponte + 1)
        for posicao in range(inicio, fim):
            conteudo[posicao] = True
    corridas = _corridas(conteudo)
    if not corridas:
        return []
    gap_documento = max(ponte + 1, int(round(total * intervalo_documento)))
    fundidas = [corridas[0]]
    for inicio, fim in corridas[1:]:
        anterior_inicio, anterior_fim = fundidas[-1]
        if inicio - anterior_fim < gap_documento:
            fundidas[-1] = (anterior_inicio, fim)
        else:
            fundidas.append((inicio, fim))
    altura_min = max(4, int(round(total * altura_minima)))
    mantidas = _absorver_faixas_curtas(fundidas, total, altura_min, gap_documento)
    faixas = []
    for inicio, fim in mantidas:
        if fim <= inicio:
            continue
        faixas.append(
            {
                "x": 0.0,
                "y": round(inicio / total, 4),
                "largura": 1.0,
                "altura": round((fim - inicio) / total, 4),
            }
        )
    return faixas


def faixas_da_imagem(imagem) -> list[dict]:
    """Limites visuais de uma página rasterizada, com recorte horizontal da tinta."""
    densidades = densidades_das_linhas(imagem)
    faixas = faixas_por_densidade(densidades)
    largura, altura = imagem.size
    for faixa in faixas:
        x, largura_relativa = _limites_horizontais(imagem, faixa["y"], faixa["y"] + faixa["altura"])
        faixa["x"] = x
        faixa["largura"] = largura_relativa
        faixa["pixels"] = {"largura": largura, "altura": altura}
    return faixas


def densidades_das_linhas(imagem) -> list[float]:
    cinza = imagem.convert("L")
    largura, altura = cinza.size
    pixels = cinza.load()
    densidades = []
    for y in range(altura):
        escuros = 0
        amostras = 0
        for x in range(0, largura, 2):
            amostras += 1
            if pixels[x, y] < 180:
                escuros += 1
        densidades.append(escuros / amostras if amostras else 0.0)
    return densidades


def _corridas(conteudo: list[bool]) -> list[tuple[int, int]]:
    corridas = []
    inicio = None
    for indice, ativo in enumerate(conteudo):
        if ativo and inicio is None:
            inicio = indice
        elif not ativo and inicio is not None:
            corridas.append((inicio, indice))
            inicio = None
    if inicio is not None:
        corridas.append((inicio, len(conteudo)))
    return corridas


def _absorver_faixas_curtas(
    corridas: list[tuple[int, int]],
    total: int,
    altura_min: int,
    gap_max: int,
) -> list[tuple[int, int]]:
    mantidas = [(inicio, fim) for inicio, fim in corridas if fim - inicio >= altura_min]
    for inicio, fim in corridas:
        if fim - inicio >= altura_min:
            continue
        if inicio > total * 0.96:
            continue
        if not mantidas:
            continue
        melhor = None
        distancia = None
        for indice, (mantido_inicio, mantido_fim) in enumerate(mantidas):
            if fim <= mantido_inicio:
                atual = mantido_inicio - fim
            elif inicio >= mantido_fim:
                atual = inicio - mantido_fim
            else:
                atual = 0
            if distancia is None or atual < distancia:
                distancia = atual
                melhor = indice
        if melhor is None or distancia is None or distancia > gap_max:
            continue
        mantido_inicio, mantido_fim = mantidas[melhor]
        mantidas[melhor] = (min(mantido_inicio, inicio), max(mantido_fim, fim))
    mantidas.sort()
    return mantidas


def _limites_horizontais(imagem, y0: float, y1: float) -> tuple[float, float]:
    cinza = imagem.convert("L")
    largura, altura = cinza.size
    pixels = cinza.load()
    y_ini = max(0, int(y0 * altura))
    y_fim = min(altura, max(y_ini + 1, int(y1 * altura)))
    passo = 2
    ativos = []
    for x in range(0, largura, passo):
        escuros = 0
        amostras = 0
        for y in range(y_ini, y_fim, 2):
            amostras += 1
            if pixels[x, y] < 180:
                escuros += 1
        if amostras and escuros / amostras >= 0.01:
            ativos.append(x)
    if not ativos:
        return 0.0, 1.0
    margem = max(8, int(largura * 0.01))
    esquerda = max(0, ativos[0] - margem) / largura
    direita = min(largura, ativos[-1] + passo + margem) / largura
    return round(esquerda, 4), round(max(0.05, direita - esquerda), 4)
