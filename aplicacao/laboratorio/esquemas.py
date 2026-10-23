"""Esquemas tipados por categoria documental. Campos ausentes permanecem vazios."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CampoEsquema:
    chave: str
    rotulo: str
    obrigatorio: bool = False
    condicional: bool = False


ESQUEMAS: dict[str, tuple[CampoEsquema, ...]] = {
    "holerite": (
        CampoEsquema("empregador", "Empregador", True),
        CampoEsquema("cnpj_empregador", "CNPJ do empregador"),
        CampoEsquema("funcionario", "Funcionário", True),
        CampoEsquema("matricula", "Matrícula ou código funcional"),
        CampoEsquema("identificadores", "Identificadores relevantes"),
        CampoEsquema("cargo", "Cargo/função"),
        CampoEsquema("cbo", "CBO"),
        CampoEsquema("competencia", "Competência", True),
        CampoEsquema("referencia_pagamento", "Referência de pagamento"),
        CampoEsquema("data_admissao", "Data de admissão", condicional=True),
        CampoEsquema("salario_base", "Salário-base"),
        CampoEsquema("rubricas_proventos", "Rubricas de proventos"),
        CampoEsquema("rubricas_descontos", "Rubricas de descontos"),
        CampoEsquema("total_proventos", "Total de proventos", True),
        CampoEsquema("total_descontos", "Total de descontos", True),
        CampoEsquema("valor_liquido", "Valor líquido", True),
        CampoEsquema("irrf", "IRRF", condicional=True),
        CampoEsquema("inss", "INSS", condicional=True),
        CampoEsquema("base_inss", "Base de cálculo do INSS"),
        CampoEsquema("base_fgts", "Base de cálculo do FGTS"),
        CampoEsquema("fgts_mes", "FGTS do mês"),
        CampoEsquema("base_irrf", "Base de cálculo do IRRF"),
        CampoEsquema("bases_calculo", "Bases de cálculo informadas"),
        CampoEsquema("data_recebimento", "Data de recebimento"),
        CampoEsquema("assinaturas", "Assinatura da trabalhadora"),
        CampoEsquema("responsavel_atesto", "Responsável pelo atesto"),
        CampoEsquema("cpf_atesto", "CPF do responsável pelo atesto"),
        CampoEsquema("liquido_calculado", "Líquido calculado (proventos − descontos)"),
    ),
    "comprovante_bancario": (
        CampoEsquema("instituicao", "Instituição financeira", True),
        CampoEsquema("tipo_operacao", "Tipo de operação"),
        CampoEsquema("titular_origem", "Titular da conta de origem"),
        CampoEsquema("agencia_origem", "Agência de origem"),
        CampoEsquema("conta_origem", "Conta de origem"),
        CampoEsquema("beneficiario", "Beneficiário", True),
        CampoEsquema("agencia_destino", "Agência de destino"),
        CampoEsquema("conta_destino", "Conta de destino"),
        CampoEsquema("dados_destino", "Dados de destino"),
        CampoEsquema("data_hora", "Data da transferência", True),
        CampoEsquema("hora_operacao", "Horário da operação"),
        CampoEsquema("data_hora_impressao", "Data/hora de impressão ou consulta"),
        CampoEsquema("valor", "Valor", True),
        CampoEsquema("numero_documento", "Número do documento"),
        CampoEsquema("numero_documento_adicional", "Número adicional do documento"),
        CampoEsquema("autenticacao", "Código de autenticação"),
        CampoEsquema("identificadores", "Identificadores e autenticação"),
        CampoEsquema("situacao", "Situação da transação", condicional=True),
    ),
    "rescisao": (
        CampoEsquema("empregador", "Empregador", True),
        CampoEsquema("trabalhador", "Trabalhador", True),
        CampoEsquema("dados_vinculo", "Dados do vínculo"),
        CampoEsquema("data_admissao", "Data de admissão"),
        CampoEsquema("data_aviso", "Data do aviso"),
        CampoEsquema("data_desligamento", "Data de desligamento", True),
        CampoEsquema("motivo", "Motivo e código de afastamento"),
        CampoEsquema("verbas_rescisorias", "Verbas rescisórias individualizadas"),
        CampoEsquema("total_bruto", "Total bruto"),
        CampoEsquema("deducoes", "Deduções"),
        CampoEsquema("total_liquido", "Total líquido lido"),
        CampoEsquema("liquido_calculado", "Líquido calculado"),
        CampoEsquema("assinaturas", "Assinaturas"),
    ),
    "quitacao": (
        CampoEsquema("empregador", "Empregador"),
        CampoEsquema("trabalhador", "Trabalhador", True),
        CampoEsquema("valor_quitado", "Valor quitado"),
        CampoEsquema("data_admissao", "Data de admissão"),
        CampoEsquema("data_aviso", "Data do aviso prévio"),
        CampoEsquema("data_afastamento", "Data de Afastamento"),
        CampoEsquema("data", "Data da quitação"),
        CampoEsquema("assinaturas", "Assinaturas"),
    ),
    "dispensa": (
        CampoEsquema("empregador", "Empregador"),
        CampoEsquema("trabalhador", "Trabalhador", True),
        CampoEsquema("data_comunicacao", "Data da comunicação"),
        CampoEsquema("protocolo", "Protocolo"),
        CampoEsquema("motivo", "Motivo"),
        CampoEsquema("comprovante_recebimento", "Comprovante de recebimento", condicional=True),
    ),
    "darf": (
        CampoEsquema("contribuinte", "Contribuinte", True),
        CampoEsquema("cnpj", "CNPJ", True),
        CampoEsquema("codigo_receita", "Código da receita", True),
        CampoEsquema("periodo_apuracao", "Período de apuração"),
        CampoEsquema("vencimento", "Vencimento"),
        CampoEsquema("principal", "Principal"),
        CampoEsquema("multa", "Multa"),
        CampoEsquema("juros", "Juros"),
        CampoEsquema("total", "Total", True),
        CampoEsquema("numero_documento", "Número do documento"),
        CampoEsquema("codigo_barras", "Código de barras"),
    ),
    "comprovante_darf": (
        CampoEsquema("instituicao", "Instituição financeira", True),
        CampoEsquema("data_pagamento", "Data do pagamento"),
        CampoEsquema("valor", "Valor", True),
        CampoEsquema("codigo_receita", "Código da receita"),
        CampoEsquema("periodo_apuracao", "Período de apuração"),
        CampoEsquema("cnpj", "CNPJ"),
        CampoEsquema("numero_documento", "Número do documento"),
        CampoEsquema("autenticacao", "Autenticação"),
        CampoEsquema("referencia", "Referência à obrigação"),
    ),
    "fgts": (
        CampoEsquema("competencia", "Competência", True),
        CampoEsquema("empregador", "Identificação do empregador", True),
        CampoEsquema("tipo_guia", "Tipo de guia"),
        CampoEsquema("base_recolhimento", "Base de recolhimento"),
        CampoEsquema("valor_recolhimento", "Valor de recolhimento", True),
        CampoEsquema("encargos", "Encargos"),
        CampoEsquema("vencimento", "Vencimento"),
        CampoEsquema("data_pagamento", "Data de pagamento", condicional=True),
        CampoEsquema("autenticacao", "Autenticação"),
        CampoEsquema("abrangencia", "Abrangência coletiva ou individual", condicional=True),
    ),
    "extrato": (
        CampoEsquema("instituicao", "Instituição financeira"),
        CampoEsquema("titular", "Titular"),
        CampoEsquema("periodo", "Período"),
        CampoEsquema("saldo_inicial", "Saldo inicial"),
        CampoEsquema("saldo_final", "Saldo final"),
    ),
    "financeiro": (
        CampoEsquema("titulo", "Título"),
        CampoEsquema("periodo", "Período"),
        CampoEsquema("totais", "Totais informados"),
    ),
    "administrativo": (
        CampoEsquema("titulo", "Título"),
        CampoEsquema("identificador", "Identificador administrativo"),
        CampoEsquema("data", "Data"),
    ),
    "folha": (
        CampoEsquema("competencia", "Competência"),
        CampoEsquema("empregador", "Empregador"),
        CampoEsquema("total_liquido", "Total líquido"),
        CampoEsquema("quantidade_trabalhadores", "Quantidade de trabalhadores"),
    ),
    "generico": (
        CampoEsquema("titulo", "Título observado"),
        CampoEsquema("observacao", "Observação"),
    ),
}


def esquema_do_tipo(codigo_tipo: str) -> tuple[CampoEsquema, ...]:
    from aplicacao.laboratorio.catalogo import CATALOGO_POR_CODIGO

    item = CATALOGO_POR_CODIGO.get(codigo_tipo)
    if item is None:
        return ESQUEMAS["generico"]
    return ESQUEMAS.get(item.esquema, ESQUEMAS["generico"])
