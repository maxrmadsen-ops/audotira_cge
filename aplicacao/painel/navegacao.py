from dataclasses import dataclass

from aplicacao.usuarios.acesso import pode_administrar


@dataclass(frozen=True)
class ItemMenu:
    rotulo: str
    url: str
    disponivel: bool
    identificador: str
    grupo: str
    ativo: bool = False
    contagem: int | None = None


MODULOS_PREPARADOS = ()

MODULOS_POR_SLUG = {slug: (rotulo, onda) for slug, rotulo, onda in MODULOS_PREPARADOS}


def construir_menu(usuario) -> list[ItemMenu]:
    if not getattr(usuario, "is_authenticated", False):
        return []

    itens = [
        ItemMenu("Painel", "/", True, "painel", "analise"),
        ItemMenu("Prestações de Contas", "/prestacoes/", True, "prestacoes-de-contas", "analise"),
        ItemMenu("Documentos", "/documentos/", True, "documentos", "analise"),
        ItemMenu("Normas", "/normas/", True, "normas", "analise"),
        ItemMenu("Regras", "/regras/", True, "regras", "analise"),
        ItemMenu("Inteligência Artificial", "/ia/", True, "inteligencia-artificial", "inteligencia"),
        ItemMenu("Achados", "/achados/", True, "achados", "inteligencia"),
        ItemMenu("Pré-Análises", "/pre-analises/", True, "pre-analises", "inteligencia"),
        ItemMenu("Avaliação", "/avaliacao/", True, "avaliacao", "inteligencia"),
        ItemMenu("FinOps", "/finops/", True, "finops", "gestao"),
    ]
    for slug, rotulo, _onda in MODULOS_PREPARADOS:
        itens.append(ItemMenu(rotulo, f"/modulos/{slug}/", False, slug, "gestao"))

    if pode_administrar(usuario):
        itens.append(ItemMenu("Administração", "/administracao/", True, "administracao", "gestao"))
        itens.append(ItemMenu("Saúde do Sistema", "/saude/", True, "saude", "gestao"))
    return itens
