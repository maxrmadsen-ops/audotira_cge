from django import template

from aplicacao.laboratorio.catalogo import rotulo_tipo

register = template.Library()


@register.filter
def tipo_documental(codigo: str) -> str:
    return rotulo_tipo(codigo or "")


@register.filter
def pct(valor) -> str:
    try:
        return f"{float(valor) * 100:.4f}"
    except (TypeError, ValueError):
        return "0"
