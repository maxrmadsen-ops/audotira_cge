from dataclasses import replace

from aplicacao.configuracao.versao import NOME_APLICACAO, ONDA_ATUAL, VERSAO_APLICACAO
from aplicacao.documentos.integracoes import INTEGRACOES, METADADOS_ENTRADA
from aplicacao.documentos.integracoes import INTEGRACOES, METADADOS_ENTRADA
from aplicacao.painel.navegacao import GRUPOS_MENU, construir_menu


def _ativo(url: str, caminho: str) -> bool:
    if url == "/":
        return caminho == "/"
    if url == "/ia/" and caminho.startswith("/ia/prompts"):
        return False
    return caminho == url or caminho.startswith(url)


def _contagens(usuario=None) -> dict[str, int]:
    from aplicacao.achados.models import Achado
    from aplicacao.pareceres.models import PreAnaliseTecnica
    from aplicacao.usuarios.acesso import prestacoes_visiveis

    if usuario is not None:
        ids = prestacoes_visiveis(usuario).values("pk")
        return {
            "achados": Achado.objects.filter(prestacao_contas_id__in=ids).count(),
            "pre-analises": PreAnaliseTecnica.objects.filter(prestacao_contas_id__in=ids).count(),
        }
    return {
        "achados": Achado.objects.count(),
        "pre-analises": PreAnaliseTecnica.objects.count(),
    }


def interface(request):
    usuario = getattr(request, "user", None)
    caminho = getattr(request, "path", "") or ""
    autenticado = getattr(usuario, "is_authenticated", False)
    marcas = _contagens(usuario if autenticado else None) if autenticado else {}
    itens = []
    for item in construir_menu(usuario):
        contagem = marcas.get(item.identificador)
        itens.append(replace(item, ativo=_ativo(item.url, caminho), contagem=contagem or None))
    return {
        "nome_aplicacao": NOME_APLICACAO,
        "versao_aplicacao": VERSAO_APLICACAO,
        "onda_atual": ONDA_ATUAL,
        "itens_menu": itens,
        "grupos_menu": GRUPOS_MENU,
        "integracoes": INTEGRACOES,
        "metadados_entrada": METADADOS_ENTRADA,
    }
