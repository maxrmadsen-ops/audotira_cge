from django import template

from aplicacao.laboratorio.catalogo import rotulo_tipo

register = template.Library()


@register.filter
def tipo_documental(codigo: str) -> str:
    return rotulo_tipo(codigo or "")


@register.simple_tag
def rotulo_segmentacao(regiao) -> str:
    from aplicacao.laboratorio.apresentacao import rotulo_metodo

    return rotulo_metodo(regiao.metodo_deteccao, regiao.estado_classificacao)


@register.filter
def pct(valor) -> str:
    try:
        return f"{float(valor) * 100:.4f}"
    except (TypeError, ValueError):
        return "0"


@register.filter
def coordenada(valor) -> str:
    """Ponto decimal fixo. O navegador em pt-BR não pode receber vírgula aqui."""
    try:
        return f"{float(valor):.6f}"
    except (TypeError, ValueError):
        return ""
