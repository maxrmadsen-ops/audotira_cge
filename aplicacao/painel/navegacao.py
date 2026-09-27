from dataclasses import dataclass

from aplicacao.usuarios.acesso import pode_administrar


@dataclass(frozen=True)
class ItemMenu:
    rotulo: str
    url: str
    disponivel: bool
    identificador: str


MODULOS_PREPARADOS = (
    ("pre-analises", "Pré-Análises", "Onda 7"),
    ("avaliacao", "Avaliação IA × Técnico", "Onda 8"),
    ("finops", "FinOps", "Onda 9"),
)

MODULOS_POR_SLUG = {slug: (rotulo, onda) for slug, rotulo, onda in MODULOS_PREPARADOS}


def construir_menu(usuario) -> list[ItemMenu]:
    if not getattr(usuario, "is_authenticated", False):
        return []

    itens = [
        ItemMenu("Painel", "/", True, "painel"),
        ItemMenu("Prestações de Contas", "/prestacoes/", True, "prestacoes-de-contas"),
        ItemMenu("Documentos", "/documentos/", True, "documentos"),
        ItemMenu("Normas", "/normas/", True, "normas"),
        ItemMenu("Regras", "/regras/", True, "regras"),
        ItemMenu("Laboratório de IA", "/ia/laboratorio/", True, "laboratorio-ia"),
        ItemMenu("Achados", "/achados/", True, "achados"),
    ]
    for slug, rotulo, _onda in MODULOS_PREPARADOS:
        itens.append(ItemMenu(rotulo, f"/modulos/{slug}/", False, slug))

    if pode_administrar(usuario):
        itens.append(ItemMenu("Administração", "/administracao/", True, "administracao"))
        itens.append(ItemMenu("Saúde do Sistema", "/saude/", True, "saude"))
    return itens
