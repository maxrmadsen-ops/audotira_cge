import re
from dataclasses import replace
from urllib.parse import parse_qs

from aplicacao.configuracao.versao import NOME_APLICACAO, ONDA_ATUAL, VERSAO_APLICACAO
from aplicacao.documentos.integracoes import INTEGRACOES, METADADOS_ENTRADA
from aplicacao.painel.navegacao import construir_menu, grupos_para


def _ativo(url: str, caminho: str) -> bool:
    if url == "/":
        return caminho == "/"
    if url.rstrip("/") == "/prestacoes":
        return caminho.rstrip("/") == "/prestacoes"
    if url == "/ia/" and caminho.startswith("/ia/prompts"):
        return False
    return caminho == url or caminho.startswith(url)


def _prestacao_contextual(usuario, caminho: str):
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return None
    from aplicacao.prestacoes_contas.models import PrestacaoContas
    from aplicacao.usuarios.acesso import pode_ver_prestacao

    achado = re.match(r"^/prestacoes/(\d+)(?:/|$)", caminho or "")
    prestacao = PrestacaoContas.objects.filter(pk=int(achado.group(1))).first() if achado else None
    if prestacao is None:
        lote = re.match(r"^/laboratorio/lotes/(\d+)(?:/|$)", caminho or "")
        if lote:
            from aplicacao.laboratorio.models import LoteLaboratorio

            item = LoteLaboratorio.objects.select_related("prestacao_parceria").filter(pk=int(lote.group(1))).first()
            prestacao = item.prestacao_parceria if item is not None else None
    if prestacao is None or not pode_ver_prestacao(usuario, prestacao):
        return None
    return prestacao


def _chave_navegacao(caminho: str, consulta) -> str:
    if hasattr(consulta, "get"):
        aba = consulta.get("aba") or "geral"
    else:
        aba = (parse_qs(consulta or "").get("aba") or ["geral"])[0]
    if "/preparacao/instrumento/" in caminho:
        return "instrumento"
    if "/preparacao/base-normativa/" in caminho:
        return "base"
    if "/conferencia/" in caminho:
        return "plano"
    if "/conferencia-integrada/" in caminho:
        return "conferencia_integrada"
    if "/conciliacao/" in caminho:
        return "conciliacao"
    if "/laboratorio/" in caminho or re.match(r"^/prestacoes/\d+/laboratorio/?", caminho or ""):
        return "laboratorio"
    if "/etapa/prestacoes-parciais/" in caminho:
        return "parciais"
    if "/etapa/prestacao-final/" in caminho:
        return "final"
    if "/etapa/regras-validacao/" in caminho:
        return "regras"
    if "/parecer-final/" in caminho:
        return "parecer"
    if re.match(r"^/prestacoes/\d+/?$", caminho):
        return {
            "geral": "geral",
            "plano": "plano",
            "documentos": "documentos",
            "financeiro": "financeiro",
            "diligencias": "diligencias",
            "analise": "verificacoes",
            "achados": "achados",
            "pre-analise": "pre",
            "linha-do-tempo": "linha",
            "folha": "folha",
            "avaliacao": "avaliacao",
        }.get(aba, "")
    return ""


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
    prestacao = _prestacao_contextual(usuario if autenticado else None, caminho)
    marcas = _contagens(usuario if autenticado else None) if autenticado else {}
    chave = _chave_navegacao(caminho, getattr(request, "GET", {}))
    itens = []
    for item in construir_menu(usuario, prestacao):
        contagem = marcas.get(item.identificador)
        ativo = item.chave == chave if item.chave else _ativo(item.url, caminho)
        itens.append(replace(item, ativo=ativo, contagem=contagem or None))
    return {
        "nome_aplicacao": NOME_APLICACAO,
        "versao_aplicacao": VERSAO_APLICACAO,
        "onda_atual": ONDA_ATUAL,
        "itens_menu": itens,
        "grupos_menu": grupos_para(prestacao),
        "processo_menu": prestacao,
        "integracoes": INTEGRACOES,
        "metadados_entrada": METADADOS_ENTRADA,
    }
