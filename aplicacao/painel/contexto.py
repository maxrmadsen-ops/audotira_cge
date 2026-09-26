from aplicacao.configuracao.versao import NOME_APLICACAO, ONDA_ATUAL, VERSAO_APLICACAO
from aplicacao.painel.navegacao import construir_menu


def interface(request):
    usuario = getattr(request, "user", None)
    return {
        "nome_aplicacao": NOME_APLICACAO,
        "versao_aplicacao": VERSAO_APLICACAO,
        "onda_atual": ONDA_ATUAL,
        "itens_menu": construir_menu(usuario),
    }
