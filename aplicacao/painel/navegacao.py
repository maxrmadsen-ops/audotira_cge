from dataclasses import dataclass

from django.urls import reverse

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
    futuro: bool = False
    parcial: bool = False
    chave: str = ""


MODULOS_PREPARADOS = ()

MODULOS_POR_SLUG = {slug: (rotulo, onda) for slug, rotulo, onda in MODULOS_PREPARADOS}


def grupos_para(prestacao) -> tuple[tuple[str, str, bool], ...]:
    if prestacao is None:
        return (
            ("painel", "Painel", True),
            ("gestao", "Processos", False),
            ("analise", "Análise", False),
            ("institucional", "Base Normativa Institucional", True),
            ("governanca", "Governança e configurações", False),
        )
    return (
        ("painel", "Painel", True),
        ("gestao", "Processos", True),
        ("preparacao", "Preparação da Parceria", False),
        ("execucao", "Execução e Comprovação", False),
        ("analise_processo", "Análise Assistida", False),
        ("fila", "Minha fila", True),
        ("institucional", "Base Normativa Institucional", True),
        ("governanca", "Governança e configurações", False),
    )


def construir_menu(usuario, prestacao=None) -> list[ItemMenu]:
    if not getattr(usuario, "is_authenticated", False):
        return []
    itens = [
        ItemMenu(
            "Painel Geral",
            "/",
            True,
            "painel",
            "painel",
            descricao="Cockpit da operação. Mostra a situação geral e abre a lista que compõe cada total.",
        ),
        ItemMenu(
            "Processos",
            "/prestacoes/",
            True,
            "prestacoes-de-contas",
            "gestao",
            descricao="Lista dos processos visíveis para este usuário.",
        ),
    ]
    if prestacao is None:
        itens.extend(_itens_sem_processo())
    else:
        itens.extend(_itens_do_processo(prestacao))
        itens.extend(_atalhos_globais("governanca"))
    itens.extend(_governanca(usuario))
    return itens


def _itens_sem_processo() -> list[ItemMenu]:
    return [
        ItemMenu(
            "Documentos",
            "/documentos/",
            True,
            "documentos",
            "gestao",
            descricao="Entrada manual e consulta dos documentos. A classificação não se confunde com a origem.",
        ),
        ItemMenu(
            "Minha fila",
            "/pendencias/",
            True,
            "pendencias",
            "analise",
            descricao="Pendências de revisão, informações ausentes e divergências. Ausência de evidência não é irregularidade.",
        ),
        *_atalhos_globais("analise"),
        ItemMenu(
            "Base Normativa Institucional",
            "/normas/",
            True,
            "normas",
            "institucional",
            descricao="Normas institucionais. Cadastro, conferência, vigência e aplicabilidade ao processo são decisões distintas.",
        ),
    ]


def _itens_do_processo(prestacao) -> list[ItemMenu]:
    pk = prestacao.pk
    detalhe = reverse("prestacoes_contas:detalhe", kwargs={"pk": pk})

    def aba(codigo: str) -> str:
        return f"{detalhe}?aba={codigo}"

    return [
        ItemMenu("Identificação da Parceria", aba("geral"), True, "prestacoes-de-contas", "preparacao", chave="geral", descricao="Identificação do processo, das entidades e do estado atual."),
        ItemMenu("Instrumento", reverse("instrumentos:instrumento", kwargs={"pk": pk}), True, "documentos", "preparacao", chave="instrumento", descricao="Termo e campos extraídos. A conferência humana não é automática."),
        ItemMenu("Base Normativa", reverse("instrumentos:base_normativa", kwargs={"pk": pk}), True, "normas", "preparacao", chave="base", descricao="Normas vinculadas a este processo."),
        ItemMenu("Plano de Trabalho", aba("plano"), True, "documentos", "preparacao", chave="plano", descricao="Resumo, metas, despesas previstas, cronograma e documento original."),
        ItemMenu("Linha do tempo", aba("linha-do-tempo"), True, "painel", "preparacao", chave="linha", descricao="Histórico registrado deste processo."),
        ItemMenu("Documentos", aba("documentos"), True, "documentos", "execucao", chave="documentos", descricao="Entrada e classificação dos PDFs deste processo. Não é a prestação de contas parcial."),
        ItemMenu("Laboratório documental", reverse("laboratorio:processo", kwargs={"pk": pk}), True, "documentos", "execucao", chave="laboratorio", descricao="Inventário, classificação por região, extração tipada e curadoria da prestação parcial."),
        ItemMenu("Prestações de Contas Parciais", reverse("prestacoes_contas:etapa_futura", kwargs={"pk": pk, "slug": "prestacoes-parciais"}), True, "pendencias", "execucao", chave="parciais", futuro=True, descricao="Etapa futura. O laboratório documental já recebe a amostra; esta etapa permanece sem workflow completo."),
        ItemMenu("Financeiro", aba("financeiro"), True, "finops", "execucao", chave="financeiro", parcial=True, descricao="Registros já informados. A execução financeira ainda não foi apurada."),
        ItemMenu("Folha de pagamento", aba("folha"), True, "administracao", "execucao", chave="folha", descricao="Folha vinculada a este processo."),
        ItemMenu("Diligências", aba("diligencias"), True, "diligencia", "execucao", chave="diligencias", descricao="Diligências já registradas. Esta tela não dispara diligência externa."),
        ItemMenu("Verificações", aba("analise"), True, "regras", "analise_processo", chave="verificacoes", descricao="Execução das regras neste processo. Não conclui a prestação."),
        ItemMenu("Prestação de Contas Final", reverse("prestacoes_contas:etapa_futura", kwargs={"pk": pk, "slug": "prestacao-final"}), True, "avaliacao", "analise_processo", chave="final", futuro=True, descricao="Etapa futura. As verificações atuais continuam em Verificações."),
        ItemMenu("Achados", aba("achados"), True, "achado", "analise_processo", chave="achados", descricao="Achados para concordar ou discordar. Não é o catálogo de regras."),
        ItemMenu("Regras e Validação", reverse("prestacoes_contas:etapa_futura", kwargs={"pk": pk, "slug": "regras-validacao"}), True, "regras", "analise_processo", chave="regras", futuro=True, descricao="Etapa futura. Regras e achados atuais permanecem nas telas existentes."),
        ItemMenu("Pré-análise", aba("pre-analise"), True, "pre-analise", "analise_processo", chave="pre", descricao="Pré-análise técnica. Não é parecer administrativo."),
        ItemMenu("Parecer", reverse("pareceres:parecer_final", kwargs={"prestacao_pk": pk}), True, "avaliacao", "analise_processo", chave="parecer", descricao="Parecer final. A conclusão administrativa permanece humana."),
        ItemMenu("Avaliação IA × técnico", aba("avaliacao"), True, "avaliacao", "analise_processo", chave="avaliacao", descricao="Comparação entre a sugestão e a decisão humana."),
        ItemMenu("Minha fila", "/pendencias/", True, "pendencias", "fila", descricao="Pendências de revisão, informações ausentes e divergências. Ausência de evidência não é irregularidade."),
        ItemMenu("Base Normativa Institucional", "/normas/", True, "normas", "institucional", descricao="Normas institucionais. Cadastro, conferência, vigência e aplicabilidade ao processo são decisões distintas."),
    ]


def _atalhos_globais(grupo: str) -> list[ItemMenu]:
    return [
        ItemMenu("Achados", "/achados/", True, "achados", grupo, descricao="Fatos e divergências para concordância ou discordância do auditor."),
        ItemMenu("Pré-análises", "/pre-analises/", True, "pre-analises", grupo, descricao="Síntese assistida. Não é o parecer nem a aprovação da prestação."),
        ItemMenu("Revisões", "/painel/revisao/", True, "revisoes", grupo, descricao="Indicadores da revisão humana. A decisão continua no item do processo."),
        ItemMenu("Avaliação IA × técnico", "/avaliacao/", True, "avaliacao", grupo, descricao="Comparação entre o resultado assistido e a avaliação do técnico."),
    ]


def _governanca(usuario) -> list[ItemMenu]:
    itens = [
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
