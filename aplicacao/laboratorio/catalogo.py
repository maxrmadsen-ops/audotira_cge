"""Catálogo extensível de tipos documentais do laboratório."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoDocumentalCatalogo:
    codigo: str
    rotulo: str
    descricao: str
    esquema: str
    palavras_chave: tuple[str, ...] = ()


CATALOGO_TIPOS: tuple[TipoDocumentalCatalogo, ...] = (
    TipoDocumentalCatalogo(
        "checklist_documental",
        "Checklist documental",
        "Lista de verificação dos documentos da prestação parcial.",
        "administrativo",
        ("checklist", "check list", "lista de verificação", "lista de verificacao"),
    ),
    TipoDocumentalCatalogo(
        "oficio_encaminhamento",
        "Ofício de encaminhamento",
        "Ofício que encaminha a prestação de contas.",
        "administrativo",
        ("ofício", "oficio", "encaminhamento"),
    ),
    TipoDocumentalCatalogo(
        "relatorio_execucao_objeto",
        "Relatório de execução do objeto",
        "Relatório descritivo da execução do objeto da parceria.",
        "administrativo",
        ("relatório de execução", "relatorio de execução", "relatorio de execucao", "execução do objeto"),
    ),
    TipoDocumentalCatalogo(
        "balancete",
        "Balancete",
        "Demonstrativo contábil de receitas e despesas.",
        "financeiro",
        ("balancete",),
    ),
    TipoDocumentalCatalogo(
        "comprovante_transferencia",
        "Comprovante de transferência",
        "Comprovante bancário de transferência, TED, DOC ou PIX.",
        "comprovante_bancario",
        (
            "comprovante de transferência",
            "comprovante de transferencia",
            "transferência realizada",
            "transferencia realizada",
            "ted ",
            "comprovante de pagamento",
        ),
    ),
    TipoDocumentalCatalogo(
        "holerite",
        "Holerite / demonstrativo de pagamento",
        "Demonstrativo individual de proventos e descontos.",
        "holerite",
        (
            "holerite",
            "demonstrativo de pagamento",
            "contracheque",
            "líquido a receber",
            "liquido a receber",
            "total de proventos",
            "total de descontos",
        ),
    ),
    TipoDocumentalCatalogo(
        "folha_pagamento",
        "Folha de pagamento",
        "Folha coletiva de pagamento da competência.",
        "folha",
        ("folha de pagamento", "relação de pagamento"),
    ),
    TipoDocumentalCatalogo(
        "termo_rescisao",
        "Termo de rescisão de contrato de trabalho",
        "Instrumento de rescisão do vínculo empregatício.",
        "rescisao",
        ("termo de rescisão", "termo de rescisao", "rescisão do contrato", "rescisao do contrato"),
    ),
    TipoDocumentalCatalogo(
        "termo_quitacao",
        "Termo de quitação",
        "Termo de quitação das verbas rescisórias.",
        "quitacao",
        ("termo de quitação", "termo de quitacao", "quitação das verbas", "quitacao das verbas"),
    ),
    TipoDocumentalCatalogo(
        "comunicacao_dispensa",
        "Comunicação de dispensa",
        "Comunicação de dispensa ou aviso prévio ao trabalhador.",
        "dispensa",
        ("comunicação de dispensa", "comunicacao de dispensa", "aviso prévio", "aviso previo"),
    ),
    TipoDocumentalCatalogo(
        "guia_fgts",
        "Guia de FGTS",
        "Guia de recolhimento do FGTS.",
        "fgts",
        ("guia de recolhimento do fgts", "grf", "guia fgts", "recolhimento do fgts"),
    ),
    TipoDocumentalCatalogo(
        "comprovante_fgts",
        "Comprovante de recolhimento de FGTS",
        "Comprovante de pagamento da guia de FGTS.",
        "fgts",
        (
            "comprovante de recolhimento",
            "autenticação bancária",
            "autenticacao bancaria",
            "fgts pago",
            "convenio fgts",
            "convênio fgts",
        ),
    ),
    TipoDocumentalCatalogo(
        "darf",
        "DARF",
        "Documento de arrecadação de receitas federais.",
        "darf",
        (
            "documento de arrecadação",
            "documento de arrecadacao",
            "receitas federais",
            "código da receita",
            "codigo da receita",
        ),
    ),
    TipoDocumentalCatalogo(
        "comprovante_darf",
        "Comprovante bancário de DARF",
        "Comprovante de pagamento de DARF ou DARF Simples.",
        "comprovante_darf",
        (
            "comprovante de pagamento de darf",
            "pagamento de darf",
            "darf/darf simples",
            "convenio rfb-darf",
            "convênio rfb-darf",
            "reb-darf",
            "rfb-darf",
        ),
    ),
    TipoDocumentalCatalogo(
        "extrato_bancario",
        "Extrato bancário",
        "Extrato da conta bancária da parceria.",
        "extrato",
        ("extrato bancário", "extrato bancario", "saldo anterior", "saldo atual"),
    ),
    TipoDocumentalCatalogo(
        "administrativo_sgpe",
        "Documento administrativo do SGP-e",
        "Página administrativa gerada pelo SGP-e.",
        "administrativo",
        ("sgp-e", "sgpe", "sistema de gestão de processos eletrônicos", "folha de rosto"),
    ),
    TipoDocumentalCatalogo(
        "assinaturas_autenticacoes",
        "Assinaturas e autenticações",
        "Página dedicada a assinaturas digitais ou autenticações.",
        "administrativo",
        ("assinatura digital", "documento assinado digitalmente", "autenticidade"),
    ),
    TipoDocumentalCatalogo(
        "outros_nao_classificados",
        "Outros / não classificados",
        "Peça sem tipo conclusivo nesta versão do laboratório.",
        "generico",
        (),
    ),
)

CATALOGO_POR_CODIGO = {item.codigo: item for item in CATALOGO_TIPOS}


def rotulo_tipo(codigo: str) -> str:
    item = CATALOGO_POR_CODIGO.get(codigo)
    return item.rotulo if item else codigo


def escolhas_tipo() -> list[tuple[str, str]]:
    return [(item.codigo, item.rotulo) for item in CATALOGO_TIPOS]
