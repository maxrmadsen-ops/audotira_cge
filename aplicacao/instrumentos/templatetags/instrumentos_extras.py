import re

from django import template

register = template.Library()


@register.filter
def mascarar_cpf(valor: str) -> str:
    texto = valor or ""
    if not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto) and not re.fullmatch(r"\d{11}", re.sub(r"\D", "", texto) or ""):
        return texto
    return re.sub(r"\d{3}\.\d{3}\.\d{3}-\d{2}", "***.***.***-**", texto) or "***.***.***-**"
