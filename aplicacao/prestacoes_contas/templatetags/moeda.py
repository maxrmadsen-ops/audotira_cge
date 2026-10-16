from decimal import Decimal, InvalidOperation

from django import template

from aplicacao.regras.resultados import texto_moeda

register = template.Library()


@register.filter
def moeda_br(valor):
    if valor is None or valor == "":
        return "—"
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return "—"
    return "R$ " + texto_moeda(numero)


@register.filter
def classe_revisao(status):
    if status == "corrigido":
        return "estado estado-corrigido"
    if status == "confirmado":
        return "estado estado-operacional"
    if status == "aguardando_validacao":
        return "estado estado-aguardando"
    return "estado estado-aguardando"


@register.filter
def rotulo_revisao(status):
    if status == "corrigido":
        return "Corrigido"
    if status == "confirmado":
        return "Confirmado"
    if status == "aguardando_validacao":
        return "Pendente"
    return "Não identificado"
