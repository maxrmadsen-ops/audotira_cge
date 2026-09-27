"""Sugestão de redação. Não cria fato, valor, norma nem confirma achado."""

from aplicacao.achados.escolhas import Criticidade, StatusAchado
from aplicacao.inteligencia_artificial.fontes import validar_fontes
from aplicacao.inteligencia_artificial.gerenciador import GerenciadorInteligenciaArtificial, chave_idempotencia

INSTRUCAO = (
    "Você não pode introduzir nenhum fato, valor, pessoa, documento, norma, dispositivo, evidência ou conclusão "
    "que não esteja presente nas entradas fornecidas."
)


def sugerir_consolidacao(achado, gerenciador: GerenciadorInteligenciaArtificial, versao_prompt, contexto: dict):
    entrada = {
        "instrucao": INSTRUCAO,
        "titulo": achado.titulo,
        "descricao_factual": achado.descricao_factual,
        "interpretacao": achado.interpretacao,
        "materialidade_financeira": None if achado.materialidade_financeira is None else str(achado.materialidade_financeira),
        "itens": contexto.get("itens") or [],
    }
    chamada = gerenciador.executar(
        agente="consolidacao_achados",
        contexto=entrada,
        versao_prompt=versao_prompt,
        prestacao=achado.prestacao_contas,
        analise=achado.analise,
        laboratorio=True,
        chave=chave_idempotencia("consolidacao", achado.pk, versao_prompt.pk),
    )
    resposta = dict(chamada.resposta or {})
    ok, rejeitadas, _fundamentos_ok, fundamentos_rejeitados = validar_fontes(contexto, resposta)
    comprometida = (
        resposta.get("resultado") == "INCONCLUSIVO"
        or bool(resposta.get("fontes_rejeitadas"))
        or bool(rejeitadas)
        or bool(fundamentos_rejeitados)
        or not _numeros_conhecidos(achado, resposta)
    )
    if comprometida:
        resposta = {
            "resultado": "INCONCLUSIVO",
            "justificativa_resumida": "A sugestão citou fonte ou valor ausente do contexto e foi descartada.",
            "fontes_rejeitadas": rejeitadas,
        }
    else:
        resposta["fontes_utilizadas"] = ok
        resposta["resultado"] = "SUGESTAO"
    if resposta.get("criticidade") == Criticidade.CRITICA:
        resposta.pop("criticidade", None)
    resposta.pop("status", None)
    achado.sugestao_consolidacao = {
        "aceita": resposta.get("resultado") == "SUGESTAO",
        "resposta": resposta,
        "usos": [uso.pk for uso in chamada.usos],
    }
    achado.status = StatusAchado.POTENCIAL if achado.status == StatusAchado.POTENCIAL else achado.status
    achado.save(update_fields=["sugestao_consolidacao", "status"])
    return chamada


def _numeros_conhecidos(achado, resposta: dict) -> bool:
    conhecidos = set(_digitos(achado.descricao_factual) + _digitos(achado.titulo))
    if achado.materialidade_financeira is not None:
        conhecidos |= set(_digitos(str(achado.materialidade_financeira)))
    propostos = _digitos(str(resposta.get("descricao_factual") or "")) + _digitos(str(resposta.get("titulo") or "")) + _digitos(str(resposta.get("justificativa_resumida") or ""))
    return set(propostos).issubset(conhecidos or set(propostos))


def _digitos(texto: str) -> list[str]:
    return [trecho for trecho in texto.replace(",", ".").split() if any(caractere.isdigit() for caractere in trecho)]
