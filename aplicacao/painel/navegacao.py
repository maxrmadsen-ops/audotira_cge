from dataclasses import dataclass

from aplicacao.usuarios.acesso import pode_administrar
from aplicacao.usuarios.models import Usuario


@dataclass(frozen=True)
class ItemMenu:
    rotulo: str
    url: str
    disponivel: bool
    identificador: str
    grupo: str
    ativo: bool = False
    contagem: int | None = None
    descricao: str = ""


MODULOS_PREPARADOS = ()

MODULOS_POR_SLUG = {slug: (rotulo, onda) for slug, rotulo, onda in MODULOS_PREPARADOS}

GRUPOS_MENU = (
    ("painel", "Painel"),
    ("gestao", "Gestão"),
    ("analise", "Análise"),
    ("governanca", "Governança e configurações"),
)


def construir_menu(usuario) -> list[ItemMenu]:
    if not getattr(usuario, "is_authenticated", False):
        return []

    itens = [
        ItemMenu("Visão geral", "/", True, "painel", "painel", descricao="Cockpit da operação. Mostra a situação geral e abre a lista que compõe cada total."),
        ItemMenu("Processos", "/prestacoes/", True, "prestacoes-de-contas", "gestao", descricao="Acompanhamento dos processos. A jornada interna leva ao instrumento, às normas e ao plano."),
        ItemMenu("Documentos", "/documentos/", True, "documentos", "gestao", descricao="Entrada manual e consulta dos documentos. A classificação não se confunde com a origem."),
        ItemMenu("Base Normativa", "/normas/", True, "normas", "gestao", descricao="Normas institucionais. Cadastro, conferência, vigência e aplicabilidade ao processo são decisões distintas."),
        ItemMenu("Minha fila", "/pendencias/", True, "pendencias", "analise", descricao="Pendências de revisão, informações ausentes e divergências. Ausência de evidência não é irregularidade."),
        ItemMenu("Achados", "/achados/", True, "achados", "analise", descricao="Fatos e divergências para concordância ou discordância do auditor."),
        ItemMenu("Pré-análises", "/pre-analises/", True, "pre-analises", "analise", descricao="Síntese assistida. Não é o parecer nem a aprovação da prestação."),
        ItemMenu("Revisões", "/painel/revisao/", True, "revisoes", "analise", descricao="Indicadores da revisão humana. A decisão continua no item do processo."),
        ItemMenu("Avaliação IA × técnico", "/avaliacao/", True, "avaliacao", "analise", descricao="Comparação entre o resultado assistido e a avaliação do técnico."),
        ItemMenu("Regras", "/regras/", True, "regras", "governanca", descricao="Catálogo das verificações. A regra não conclui a prestação."),
        ItemMenu("Modelos", "/ia/", True, "inteligencia-artificial", "governanca", descricao="Modelos e roteamento. Nenhuma chamada daqui aprova a prestação."),
        ItemMenu("FinOps", "/finops/", True, "finops", "governanca", descricao="Consumo e custo da operação assistida."),
    ]
    if getattr(usuario, "perfil", "") in {Usuario.Perfil.ADMINISTRADOR, Usuario.Perfil.AUDITOR}:
        itens.append(ItemMenu("Prompts", "/ia/prompts/", True, "prompts", "governanca", descricao="Versões governadas dos prompts. A ativação é humana."))
    if pode_administrar(usuario):
        itens.append(ItemMenu("Administração", "/administracao/", True, "administracao", "governanca", descricao="Usuários e perfis. Não altera decisões de auditoria."))
        itens.append(ItemMenu("Saúde do Sistema", "/saude/", True, "saude", "governanca", descricao="Disponibilidade dos componentes. Não executa análise."))
    return itens
