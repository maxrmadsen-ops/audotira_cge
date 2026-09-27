"""Classificação técnica interna. Não substitui a categoria nem o texto da matriz."""

from aplicacao.regras.escolhas import CapacidadeExecucao, TipoDependencia, TipoExecucaoTecnica

T = TipoExecucaoTecnica
C = CapacidadeExecucao


def _item(tipo, capacidade, executor, **configuracao):
    configuracao = dict(configuracao)
    dependencias = configuracao.pop("dependencias", [])
    return {
        "tipo_execucao": tipo,
        "capacidade": capacidade,
        "executor": executor,
        "configuracao": configuracao,
        "dependencias": dependencias,
    }


def _registrar(tabela, codigos, tipo, capacidade, executor, **configuracao):
    if isinstance(codigos, str):
        codigos = (codigos,)
    for codigo in codigos:
        tabela[codigo] = _item(tipo, capacidade, executor, **configuracao)


def montar_classificacao() -> dict:
    tabela: dict = {}
    registrar = lambda *args, **kwargs: _registrar(tabela, *args, **kwargs)

    registrar("CTX-001", T.DETERMINISTICA, C.PARCIAL, "contexto", operacao="instrumento")
    registrar("CTX-002", T.DETERMINISTICA, C.PARCIAL, "contexto", operacao="objeto")
    registrar("CTX-003", T.DETERMINISTICA, C.PARCIAL, "contexto", operacao="vigencia")
    registrar("CTX-004", T.DETERMINISTICA, C.PARCIAL, "contexto", operacao="valores")
    registrar("CTX-005", T.DETERMINISTICA, C.PARCIAL, "contexto", operacao="normas")

    registrar("DOC-001", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="tipo", tipos=["termo"], nomes=["termo", "instrumento"])
    registrar("DOC-002", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="tipo", tipos=["plano_trabalho"], nomes=["plano de trabalho"])
    registrar("DOC-003", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="nome", nomes=["listar transferencia"])
    registrar("DOC-004", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="nome", nomes=["datas a serem cumpridas"])
    registrar("DOC-005", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="nome", nomes=["despesas plano"])
    registrar("DOC-006", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="nome", nomes=["monitoramento"])
    registrar("DOC-007", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="inventario")
    registrar("DOC-008", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="suporte_despesa")
    registrar("DOC-009", T.DOCUMENTAL, C.PARCIAL, "teste_cego")

    registrar("DES-001", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="suporte_despesa")
    registrar(("DES-002", "DES-005"), T.SEMANTICA, C.REQUER_IA, "semantico")
    registrar("DES-003", T.DETERMINISTICA, C.AUTOMATICA, "comparacao_valor", operacao="despesa_pagamento")
    registrar("DES-004", T.DETERMINISTICA, C.AUTOMATICA, "somatorio", operacao="documentos_pagamentos")

    registrar("PAG-001", T.DOCUMENTAL, C.PARCIAL, "documental", consulta="comprovante")
    registrar("PAG-002", T.DETERMINISTICA, C.AUTOMATICA, "comparacao_valor", operacao="pagamento_extrato")
    registrar("PAG-003", T.DETERMINISTICA, C.AUTOMATICA, "somatorio", operacao="comprovantes_extrato")
    registrar("PAG-004", T.DETERMINISTICA, C.PARCIAL, "identidade", operacao="beneficiario_pagamento")

    registrar(("FIN-001", "FIN-006", "FIN-007"), T.DETERMINISTICA, C.PARCIAL, "identidade", operacao="fornecedor")
    registrar("FIN-002", T.DETERMINISTICA, C.AUTOMATICA, "comparacao_valor", operacao="despesa_extrato")
    registrar("FIN-003", T.DETERMINISTICA, C.AUTOMATICA, "comparacao_valor", operacao="diferenca")
    registrar(("FIN-004", "FIN-005", "FIN-008", "FIN-009"), T.DETERMINISTICA, C.AUTOMATICA, "comparacao_valor", operacao="balancete")

    registrar("BAN-001", T.DETERMINISTICA, C.PARCIAL, "movimentacao", operacao="inventario")
    registrar("BAN-002", T.DETERMINISTICA, C.PARCIAL, "movimentacao", operacao="suporte_saida")
    registrar("BAN-003", T.DETERMINISTICA, C.PARCIAL, "plano", operacao="pagamento_no_plano")
    registrar("BAN-004", T.DETERMINISTICA, C.PARCIAL, "movimentacao", operacao="sem_suporte")
    registrar("BAN-005", T.DETERMINISTICA, C.PARCIAL, "movimentacao", operacao="aplicacao")

    registrar("NF-001", T.DOCUMENTAL, C.PARCIAL, "nota_fiscal")

    registrar(("VED-001", "VED-002", "VED-003", "VED-004", "VED-005", "VED-006", "VED-007", "VED-008"), T.SEMANTICA, C.REQUER_IA, "semantico")
    registrar("VED-009", T.DETERMINISTICA, C.AUTOMATICA, "comparacao_data", operacao="vigencia_despesa")
    registrar("VED-010", T.DETERMINISTICA, C.PARCIAL, "identidade", operacao="fornecedor_beneficiario")
    registrar(("VED-011", "VED-012"), T.HUMANA, C.REQUER_ANALISTA, "analista")

    registrar(("CLA-001", "CLA-004"), T.SEMANTICA, C.REQUER_IA, "semantico")
    registrar("CLA-002", T.DETERMINISTICA, C.PARCIAL, "comparacao_data", operacao="prazo")
    registrar("CLA-003", T.DETERMINISTICA, C.PARCIAL, "comparacao_data", operacao="tempestividade")

    registrar("PT-001", T.DETERMINISTICA, C.PARCIAL, "plano", operacao="despesa_no_plano")
    registrar("PT-002", T.SEMANTICA, C.REQUER_IA, "semantico")
    registrar("PT-003", T.DETERMINISTICA, C.AUTOMATICA, "plano", operacao="valores")
    registrar("PT-004", T.DETERMINISTICA, C.AUTOMATICA, "plano", operacao="diferenca")
    registrar(("PT-005", "PT-006"), T.DETERMINISTICA, C.PARCIAL, "plano", operacao="vinculo")
    registrar("PT-007", T.DETERMINISTICA, C.AUTOMATICA, "plano", operacao="apresentar")
    registrar("PT-008", T.DETERMINISTICA, C.AUTOMATICA, "plano", operacao="diferenca_informada")

    registrar(("PRI-001", "PRI-002", "PRI-003", "PRI-005", "PRI-006", "PRI-007"), T.SEMANTICA, C.REQUER_IA, "semantico")
    registrar("PRI-004", T.HUMANA, C.REQUER_IA, "semantico")
    registrar(("OBJ-001", "OBJ-002", "OBJ-003"), T.SEMANTICA, C.REQUER_IA, "semantico")

    registrar(("EFE-001", "EFE-002"), T.FORA_ESCOPO_V1, C.FORA_ESCOPO, "fora_escopo")

    registrar("PRE-001", T.DETERMINISTICA, C.AUTOMATICA, "plano", operacao="preco")
    registrar("PRE-002", T.DETERMINISTICA, C.AUTOMATICA, "plano", operacao="diferenca_preco")
    registrar("PRE-003", T.DETERMINISTICA, C.PARCIAL, "plano", operacao="detalhamento")

    registrar("CONT-001", T.DETERMINISTICA, C.PARCIAL, "contrapartida", operacao="existencia")
    registrar(
        "CONT-002",
        T.DETERMINISTICA,
        C.PARCIAL,
        "contrapartida",
        operacao="financeira",
        dependencias=[
            {
                "codigo": "CONT-001",
                "tipo": TipoDependencia.CONDICIONA,
                "parametro": {"resultado_contem": "EXISTE"},
            }
        ],
    )
    registrar(("CONT-003", "CONT-004"), T.DOCUMENTAL, C.PARCIAL, "contrapartida", operacao="evidencia")

    registrar("DEV-001", T.DETERMINISTICA, C.AUTOMATICA, "devolucao", operacao="saldo")
    registrar("DEV-002", T.DETERMINISTICA, C.AUTOMATICA, "devolucao", operacao="saldo_devolvido")
    registrar("DEV-003", T.DETERMINISTICA, C.PARCIAL, "devolucao", operacao="credito")

    registrar("ACH-001", T.DETERMINISTICA, C.PARCIAL, "achado", operacao="rastreavel")
    registrar("ACH-002", T.DETERMINISTICA, C.PARCIAL, "achado", operacao="fundamento")

    registrar("SYS-001", T.GOVERNANCA, C.AUTOMATICA, "governanca", operacao="nao_conclusivo")
    registrar("SYS-002", T.GOVERNANCA, C.AUTOMATICA, "governanca", operacao="ausencia")
    registrar("SYS-003", T.GOVERNANCA, C.AUTOMATICA, "governanca", operacao="validacao_humana")
    return tabela


CLASSIFICACAO = montar_classificacao()
