from decimal import Decimal

from aplicacao.regras.contexto import digitos
from aplicacao.regras.escolhas import (
    FONTE_EXCLUIDA_TESTE_CEGO,
    RESULTADO_SEMANTICO,
    Encaminhamento,
    REGRA_DE_OURO,
    StatusTecnico,
)
from aplicacao.regras.resultados import (
    ZERO,
    agregar,
    calculo,
    dinheiro,
    percentual,
    referencia,
    status_de,
    texto_moeda,
    ResultadoExecutor,
)


class ExecutorRegraBase:
    nome = "base"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        raise NotImplementedError


def _resultado(funcional: str, limitacao: str = "", **extras) -> ResultadoExecutor:
    return ResultadoExecutor(
        resultado_funcional=funcional,
        status_tecnico=extras.pop("status", status_de(funcional)),
        limitacao=limitacao,
        **extras,
    )


def _insuficiente(limitacao: str) -> ResultadoExecutor:
    return _resultado(
        "NÃO VERIFICÁVEL",
        limitacao,
        entradas={"dados_insuficientes": True},
        status=StatusTecnico.INCONCLUSIVO,
    )


class ExecutorContexto(ExecutorRegraBase):
    nome = "contexto"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        if operacao == "instrumento":
            instrumento = contexto.instrumento()
            if instrumento is None or not (instrumento.numero or instrumento.tipo):
                return _resultado("NÃO LOCALIZADO", "Instrumento não localizado nos dados estruturados. Nenhum dado foi presumido.")
            return _resultado(
                "IDENTIFICADO",
                referencias=[
                    referencia(
                        tipo_fonte="instrumento",
                        identificador=instrumento.id,
                        campo="numero",
                        valor_utilizado=instrumento.numero,
                        papel_na_regra="instrumento",
                    )
                ],
            )
        if operacao == "objeto":
            objeto = (contexto.prestacao.objeto or "").strip()
            instrumento = contexto.instrumento()
            if not objeto and instrumento is not None:
                objeto = (instrumento.objeto or "").strip()
            if not objeto:
                return _resultado("NÃO LOCALIZADO", "Objeto não localizado. Nenhum objeto foi presumido.")
            return _resultado(
                "IDENTIFICADO",
                referencias=[referencia(tipo_fonte="prestacao", identificador=contexto.prestacao.id, campo="objeto", valor_utilizado=objeto[:255], papel_na_regra="objeto")],
            )
        if operacao == "vigencia":
            instrumento = contexto.instrumento()
            inicio = instrumento.vigencia_inicio if instrumento else contexto.prestacao.data_inicio
            fim = instrumento.vigencia_fim if instrumento else contexto.prestacao.data_fim
            if inicio is None or fim is None:
                return _resultado("NÃO LOCALIZADO", "Vigência não documentada nos dados estruturados.")
            return _resultado(
                "IDENTIFICADO",
                referencias=[
                    referencia(
                        tipo_fonte="instrumento",
                        identificador=getattr(instrumento, "id", contexto.prestacao.id),
                        campo="vigencia",
                        valor_utilizado=f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}",
                        papel_na_regra="vigencia",
                    )
                ],
            )
        if operacao == "valores":
            instrumento = contexto.instrumento()
            pactuado = dinheiro(instrumento.valor) if instrumento else None
            informado = dinheiro(contexto.prestacao.valor_total)
            if pactuado is None or informado is None:
                return _insuficiente("Valor pactuado ou valor informado está ausente. A ausência não foi tratada como divergência.")
            if pactuado != informado:
                return _resultado(
                    "DIVERGÊNCIA",
                    "Os valores estruturados diferem. A classificação jurídica cabe ao analista.",
                    calculos=[calculo("diferenca", {"valor_pactuado": pactuado, "valor_informado": informado}, pactuado - informado, "BRL")],
                    status=StatusTecnico.DIVERGENCIA,
                )
            return _resultado("IDENTIFICADO", calculos=[calculo("igualdade", {"valor_pactuado": pactuado, "valor_informado": informado}, pactuado, "BRL")])
        if operacao == "normas":
            if contexto.data_referencia() is None:
                return _insuficiente("Sem data de referência não é possível resolver a vigência normativa.")
            resolucao = contexto.resolucao_normativa()
            if not resolucao.elegiveis:
                return _insuficiente("Nenhuma norma vigente e aplicável foi localizada para a data de referência.")
            return _resultado("NORMAS IDENTIFICADAS", referencias=contexto.referencias_normativas())
        return _insuficiente("Operação de contexto não configurada.")


class ExecutorDocumental(ExecutorRegraBase):
    nome = "documental"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        consulta = regra.configuracao.get("consulta")
        if consulta in {"tipo", "nome"}:
            encontrados = contexto.documentos_correspondentes(regra.configuracao.get("tipos"), regra.configuracao.get("nomes"))
            if encontrados:
                return _resultado("PRESENTE", referencias=contexto.referencias_documentos(encontrados, "documento_localizado"))
            return _resultado("AUSENTE", "Documento não localizado no conjunto autorizado desta execução.")
        if consulta == "inventario":
            if contexto.documentos:
                return _resultado("PRESENTE", referencias=contexto.referencias_documentos(contexto.documentos, "inventario"))
            return _resultado("AUSENTE", "Nenhum documento autorizado no conjunto de entrada.")
        if consulta == "suporte_despesa":
            pares = contexto.pares_despesa()
            if not pares:
                return _insuficiente("Não há despesas estruturadas para confrontar com documentos.")
            parciais = []
            refs = []
            for par in pares:
                if par["fiscais"]:
                    parciais.append("CONFORME")
                    refs.extend(
                        referencia(
                            tipo_fonte="documento_fiscal",
                            identificador=fiscal.id,
                            campo="numero",
                            valor_utilizado=fiscal.numero,
                            papel_na_regra="suporte_despesa",
                        )
                        for fiscal in par["fiscais"]
                    )
                else:
                    parciais.append("AUSENTE")
            if any(item == "CONFORME" for item in parciais) and any(item == "AUSENTE" for item in parciais):
                return _resultado("INCOMPLETO", "Parte das despesas não tem documento fiscal vinculado.", referencias=refs, status=StatusTecnico.INCONCLUSIVO)
            return _resultado(agregar(parciais, ok="CONFORME", divergencia="DIVERGÊNCIA", ausente="AUSENTE", inconclusivo="NÃO VERIFICÁVEL"), referencias=refs)
        if consulta == "comprovante":
            pagamentos = contexto.pagamentos()
            if not contexto.despesas() and not pagamentos:
                return _insuficiente("Não há despesas nem pagamentos estruturados.")
            if not pagamentos:
                return _resultado("AUSENTE", "Nenhum comprovante de pagamento estruturado foi localizado.")
            incompletos = [pagamento for pagamento in pagamentos if pagamento.valor is None or pagamento.data is None]
            if incompletos and len(incompletos) < len(pagamentos):
                return _resultado("INCOMPLETO", "Há pagamentos sem data ou valor.", status=StatusTecnico.INCONCLUSIVO)
            if incompletos:
                return _insuficiente("Os pagamentos localizados não têm data e valor suficientes.")
            return _resultado(
                "PRESENTE",
                referencias=[
                    referencia(tipo_fonte="pagamento", identificador=pagamento.id, campo="identificador", valor_utilizado=pagamento.identificador, papel_na_regra="comprovante")
                    for pagamento in pagamentos
                ],
            )
        return _insuficiente("Consulta documental não configurada.")


class ExecutorTesteCego(ExecutorRegraBase):
    nome = "teste_cego"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        if not contexto.modo_teste_cego:
            return _resultado(
                "APLICÁVEL EM TESTE POSTERIOR",
                "Fora do teste cego, a exclusão de relatórios com análise técnica prévia não é aplicada.",
                status=StatusTecnico.NAO_APLICAVEL,
            )
        refs = [
            referencia(
                tipo_fonte="documento",
                identificador=item["documento_id"],
                documento_id=item["documento_id"],
                campo="nome_original",
                valor_utilizado=item["nome"],
                papel_na_regra=FONTE_EXCLUIDA_TESTE_CEGO,
            )
            for item in contexto.excluidos
        ]
        return _resultado(
            "EXCLUÍDO DO ESCOPO",
            "Documentos de prestação parcial ou final com análise técnica prévia não entram no teste cego.",
            referencias=refs,
            entradas={"excluidos": [item["documento_id"] for item in contexto.excluidos]},
        )


class ExecutorComparacaoValor(ExecutorRegraBase):
    nome = "comparacao_valor"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        if operacao == "balancete":
            return _insuficiente("Não há lançamentos estruturados de balancete para confrontar com o extrato. A ausência não foi tratada como divergência.")
        if operacao == "pagamento_extrato":
            return self._pagamentos(contexto)
        if operacao == "despesa_extrato":
            return self._lados(contexto, "valor_documentado", "valor_extrato", "CONFORME", "DIVERGÊNCIA", "NÃO LOCALIZADO")
        return self._lados(contexto, "valor_documentado", "valor_pago", "SEM DIVERGÊNCIA" if operacao == "diferenca" else "CONFORME", "DIVERGÊNCIA", "NÃO LOCALIZADO", diferença=operacao == "diferenca")

    def _pagamentos(self, contexto) -> ResultadoExecutor:
        pagamentos = contexto.pagamentos()
        if not pagamentos:
            return _insuficiente("Não há pagamentos estruturados para confrontar com o extrato.")
        parciais = []
        calculos = []
        refs = []
        for pagamento in pagamentos:
            movimentos = list(pagamento.movimentacoes.all())
            extrato = somar_movimentos(movimentos)
            pago = dinheiro(pagamento.valor)
            if pago is None or extrato is None:
                parciais.append("NÃO LOCALIZADO" if movimentos or pago is not None else "NÃO VERIFICÁVEL")
                continue
            parciais.append("CONFORME" if pago == extrato else "DIVERGÊNCIA")
            calculos.append(calculo("diferenca", {"valor_pago": pago, "valor_extrato": extrato}, pago - extrato, "BRL"))
            refs.append(referencia(tipo_fonte="pagamento", identificador=pagamento.id, campo="valor", valor_utilizado=texto_moeda(pago), papel_na_regra="comprovante"))
        funcional = agregar(parciais, ok="CONFORME", divergencia="DIVERGÊNCIA", ausente="NÃO LOCALIZADO", inconclusivo="NÃO VERIFICÁVEL")
        return _resultado(funcional, referencias=refs, calculos=calculos, entradas={"dados_insuficientes": funcional == "NÃO VERIFICÁVEL"})

    def _lados(self, contexto, esquerda, direita, ok, divergencia, ausente, diferença=False) -> ResultadoExecutor:
        pares = contexto.pares_despesa()
        if not pares:
            return _insuficiente("Não há despesas estruturadas para comparar valores.")
        parciais = []
        calculos = []
        refs = []
        for par in pares:
            a = par[esquerda]
            b = par[direita]
            if a is None or b is None:
                parciais.append(ausente if (a is None) != (b is None) else "NÃO VERIFICÁVEL")
                continue
            diferente = a != b
            parciais.append(divergencia if diferente else ok)
            diferenca = a - b
            calculos.append(calculo("diferenca", {"valor_documentado": a, "valor_pago": b}, diferenca, "BRL"))
            if diferença:
                taxa = percentual(abs(diferenca), a)
                if taxa is not None:
                    calculos.append(calculo("percentual", {"diferenca": abs(diferenca), "valor_documentado": a}, taxa, "%"))
            if par["despesa"].id:
                refs.append(referencia(tipo_fonte="despesa", identificador=par["despesa"].id, campo="valor", valor_utilizado=texto_moeda(a), papel_na_regra="valor_documentado"))
        funcional = agregar([item if item != "NÃO VERIFICÁVEL" else "NÃO VERIFICÁVEL" for item in parciais], ok=ok, divergencia=divergencia, ausente=ausente, inconclusivo="NÃO VERIFICÁVEL")
        if "NÃO VERIFICÁVEL" in parciais and funcional not in {divergencia, ok}:
            funcional = "NÃO VERIFICÁVEL"
        return _resultado(
            funcional,
            "" if funcional != "NÃO VERIFICÁVEL" else "Dados insuficientes para a comparação. A ausência não foi tratada como divergência.",
            referencias=refs,
            calculos=calculos,
            entradas={"dados_insuficientes": funcional == "NÃO VERIFICÁVEL"},
        )


def somar_movimentos(movimentos):
    from aplicacao.regras.resultados import somar

    return somar(movimento.valor for movimento in movimentos)


class ExecutorSomatorio(ExecutorRegraBase):
    nome = "somatorio"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        if operacao == "documentos_pagamentos":
            pares = contexto.pares_despesa()
            documentado = somar_de(par["valor_documentado"] for par in pares)
            pago = somar_de(par["valor_pago"] for par in pares)
            esquerda, direita = "valor_documentado", "valor_pago"
        else:
            pagamentos = contexto.pagamentos()
            movimentos = [movimento for movimento in contexto.movimentacoes() if movimento.tipo == "debito"]
            documentado = somar_de(dinheiro(pagamento.valor) for pagamento in pagamentos)
            pago = somar_de(dinheiro(movimento.valor) for movimento in movimentos)
            esquerda, direita = "comprovantes", "extrato"
        if documentado is None or pago is None:
            return _insuficiente("Não há totais suficientes para o somatório. A ausência não foi tratada como divergência.")
        funcional = "CONFORME" if documentado == pago else "DIVERGÊNCIA"
        return _resultado(
            funcional,
            calculos=[calculo("diferenca_totais", {esquerda: documentado, direita: pago}, documentado - pago, "BRL")],
        )


def somar_de(valores):
    from aplicacao.regras.resultados import somar

    return somar(valor for valor in valores if valor is not None)


class ExecutorComparacaoData(ExecutorRegraBase):
    nome = "comparacao_data"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        if operacao == "vigencia_despesa":
            return self._vigencia(contexto)
        return _insuficiente("A data-limite ou a data de entrega não estão estruturadas. Nenhuma data foi presumida.")

    def _vigencia(self, contexto) -> ResultadoExecutor:
        instrumento = contexto.instrumento()
        inicio = instrumento.vigencia_inicio if instrumento else None
        fim = instrumento.vigencia_fim if instrumento else None
        if inicio is None or fim is None:
            return _insuficiente("Vigência do instrumento ausente. A despesa não foi classificada como fora da vigência.")
        datas = []
        refs = [
            referencia(
                tipo_fonte="instrumento",
                identificador=instrumento.id,
                campo="vigencia",
                valor_utilizado=f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}",
                papel_na_regra="vigencia",
            )
        ]
        for par in contexto.pares_despesa():
            for fiscal in par["fiscais"]:
                if fiscal.data_emissao:
                    datas.append(fiscal.data_emissao)
                    refs.append(referencia(tipo_fonte="documento_fiscal", identificador=fiscal.id, campo="data_emissao", valor_utilizado=f"{fiscal.data_emissao:%d/%m/%Y}", papel_na_regra="data_nf"))
        if not datas:
            return _insuficiente("Não há data de emissão de nota ou documento fiscal. A ausência não foi tratada como divergência.")
        fora = [item for item in datas if item < inicio or item > fim]
        if fora:
            return _resultado("FORA DA VIGÊNCIA", "A data de emissão está fora do período documentado do instrumento.", referencias=refs, status=StatusTecnico.DIVERGENCIA)
        return _resultado("CONFORME", referencias=refs)


class ExecutorCorrespondenciaIdentidade(ExecutorRegraBase):
    nome = "identidade"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        if operacao == "fornecedor_beneficiario":
            return self._vedacao_propria(contexto)
        if regra.codigo in {"FIN-006", "FIN-007"}:
            return _insuficiente("Não há identificador estruturado de balancete. Nome não foi tratado como identidade comprovada.")
        return self._identidade_forte(contexto)

    def _vedacao_propria(self, contexto) -> ResultadoExecutor:
        beneficiario = contexto.prestacao.beneficiario
        cnpj_beneficiario = digitos_entidade(beneficiario)
        if not cnpj_beneficiario:
            return _insuficiente("CNPJ do beneficiário ausente. O nome não foi usado como prova de identidade.")
        comparacoes = []
        for par in contexto.pares_despesa():
            fornecedor = par["despesa"].fornecedor
            cnpj_fornecedor = digitos_entidade(getattr(fornecedor, "entidade", None))
            if not cnpj_fornecedor:
                comparacoes.append("NÃO VERIFICÁVEL")
                continue
            comparacoes.append("POSSÍVEL VEDAÇÃO" if cnpj_fornecedor == cnpj_beneficiario else "NÃO IDENTIFICADA")
        if not comparacoes:
            return _insuficiente("Não há fornecedor estruturado para comparar com o beneficiário.")
        if any(item == "POSSÍVEL VEDAÇÃO" for item in comparacoes):
            return _resultado("POSSÍVEL VEDAÇÃO", "A correspondência usa CNPJ. A conclusão jurídica cabe ao analista.", entradas={"metodo": "cnpj"})
        if any(item == "NÃO VERIFICÁVEL" for item in comparacoes) and not all(item == "NÃO IDENTIFICADA" for item in comparacoes):
            return _insuficiente("Há fornecedor sem CNPJ. Nomes semelhantes não comprovam identidade.")
        return _resultado("NÃO IDENTIFICADA", "Os CNPJs comparados são distintos.", entradas={"metodo": "cnpj"})

    def _identidade_forte(self, contexto) -> ResultadoExecutor:
        pares = contexto.pares_despesa()
        if not pares:
            return _insuficiente("Não há despesa estruturada para correspondência de identidade.")
        parciais = []
        for par in pares:
            cnpj = digitos_entidade(getattr(par["despesa"].fornecedor, "entidade", None))
            identificadores = [digitos(movimento.identificador) for movimento in par["movimentos"] if digitos(movimento.identificador)]
            identificadores += [digitos(pagamento.identificador) for pagamento in par["pagamentos"] if digitos(pagamento.identificador)]
            if not cnpj or not identificadores:
                parciais.append("NÃO VERIFICÁVEL")
                continue
            if any(item == cnpj for item in identificadores):
                parciais.append("CONFORME")
            elif identificadores:
                parciais.append("DIVERGÊNCIA")
        funcional = agregar(parciais, ok="CONFORME", divergencia="DIVERGÊNCIA", ausente="NÃO LOCALIZADO", inconclusivo="NÃO VERIFICÁVEL")
        limitacao = ""
        if funcional == "NÃO VERIFICÁVEL":
            limitacao = "Sem identificador forte nas duas pontas. Nomes semelhantes não comprovam identidade."
        return _resultado(funcional, limitacao, entradas={"metodo": "cnpj" if funcional != "NÃO VERIFICÁVEL" else "insuficiente", "dados_insuficientes": funcional == "NÃO VERIFICÁVEL"})


def digitos_entidade(entidade) -> str:
    if entidade is None:
        return ""
    return digitos(getattr(entidade, "cnpj", "") or "")


class ExecutorMovimentacaoBancaria(ExecutorRegraBase):
    nome = "movimentacao"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        movimentos = contexto.movimentacoes()
        if operacao == "inventario":
            if not movimentos:
                return _insuficiente("Extrato estruturado ausente. O período não foi presumido.")
            return _resultado(
                "ANALISADO",
                "Inventário limitado aos lançamentos estruturados.",
                referencias=[referencia(tipo_fonte="movimentacao", identificador=item.id, campo="historico", valor_utilizado=item.historico, papel_na_regra="lancamento") for item in movimentos],
            )
        if operacao == "aplicacao":
            if not movimentos:
                return _insuficiente("Extrato estruturado ausente.")
            from aplicacao.regras.contexto import normalizar

            aplicadas = [item for item in movimentos if "aplicacao" in normalizar(item.historico)]
            if aplicadas:
                return _resultado("IDENTIFICADA", referencias=[referencia(tipo_fonte="movimentacao", identificador=item.id, campo="historico", valor_utilizado=item.historico, papel_na_regra="aplicacao") for item in aplicadas])
            return _resultado("NÃO IDENTIFICADA", "Nenhum lançamento estruturado traz aplicação financeira.")
        if not movimentos:
            return _insuficiente("Não há movimentação estruturada para procurar suporte.")
        sem_suporte = []
        com_suporte = []
        for movimento in movimentos:
            if movimento.tipo != "debito" and operacao == "suporte_saida":
                continue
            if movimento.pagamentos.exists():
                com_suporte.append(movimento)
            else:
                sem_suporte.append(movimento)
        if not com_suporte and not sem_suporte:
            return _insuficiente("Não há saída estruturada para verificar suporte.")
        if sem_suporte and not com_suporte:
            token = "SEM SUPORTE LOCALIZADO" if operacao == "suporte_saida" else "SEM SUPORTE"
            return _resultado(token, "A ausência no material estruturado não prova que o documento não exista.", status=StatusTecnico.ATENCAO)
        if sem_suporte:
            token = "SEM SUPORTE LOCALIZADO" if operacao == "suporte_saida" else "SEM SUPORTE"
            return _resultado(token, "Parte das movimentações não tem pagamento vinculado.", status=StatusTecnico.ATENCAO)
        token = "CONFORME" if operacao == "suporte_saida" else "SUPORTE LOCALIZADO"
        return _resultado(token)


class ExecutorPlanoTrabalho(ExecutorRegraBase):
    nome = "plano"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        itens = []
        for plano in contexto.prestacao.planos.prefetch_related("itens__despesas"):
            itens.extend(list(plano.itens.all()))
        if operacao == "detalhamento":
            if not itens:
                return _resultado("NÃO VERIFICÁVEL", "Plano sem itens estruturados.", status=StatusTecnico.INCONCLUSIVO, entradas={"dados_insuficientes": True})
            if any(item.valor_previsto is None for item in itens):
                return _resultado("NÃO VERIFICÁVEL", "Há item do plano sem valor previsto. A comparação de preço não foi forçada.", status=StatusTecnico.INCONCLUSIVO, entradas={"dados_insuficientes": True})
            return _resultado("", "O plano possui parâmetro comparável; a regra de impossibilidade não se aplica.", status=StatusTecnico.NAO_APLICAVEL)
        if operacao in {"despesa_no_plano", "pagamento_no_plano", "vinculo"}:
            despesas = contexto.despesas()
            if not despesas or not itens:
                return _insuficiente("Plano ou despesa ausentes. Nenhum vínculo foi presumido.")
            vinculados = [despesa for despesa in despesas if despesa.item_plano_id]
            if not vinculados:
                token = "NÃO LOCALIZADO" if operacao == "vinculo" else "NÃO VERIFICÁVEL"
                return _resultado(token, "Nenhuma despesa aponta para um item do plano.", status=StatusTecnico.INCONCLUSIVO, entradas={"dados_insuficientes": True})
            if len(vinculados) < len(despesas):
                token = "NÃO VERIFICÁVEL" if operacao == "vinculo" else "POSSÍVEL INCOMPATIBILIDADE"
                status = StatusTecnico.INCONCLUSIVO if token == "NÃO VERIFICÁVEL" else StatusTecnico.ATENCAO
                return _resultado(token, "Parte das despesas não está vinculada a item do plano.", status=status)
            token = "VINCULADO" if operacao == "vinculo" else "COMPATÍVEL"
            return _resultado(token)
        return self._valores(itens, operacao)

    def _valores(self, itens, operacao) -> ResultadoExecutor:
        if not itens:
            return _insuficiente("Não há itens de plano para comparar valores.")
        calculos = []
        parciais = []
        for item in itens:
            previsto = dinheiro(item.valor_previsto)
            realizado = dinheiro(item.valor_realizado)
            if previsto is None or realizado is None:
                parciais.append("NÃO VERIFICÁVEL")
                continue
            diferenca = previsto - realizado
            parciais.append("ok" if diferenca == ZERO else "dif")
            calculos.append(calculo("diferenca", {"valor_previsto": previsto, "valor_realizado": realizado}, diferenca, "BRL"))
            if operacao in {"diferenca", "diferenca_informada", "diferenca_preco"}:
                taxa = percentual(abs(diferenca), previsto)
                if taxa is not None:
                    calculos.append(calculo("percentual", {"diferenca": abs(diferenca), "valor_previsto": previsto}, taxa, "%"))
        if not parciais or all(item == "NÃO VERIFICÁVEL" for item in parciais):
            return _insuficiente("Valores previsto e realizado não estão ambos disponíveis.")
        if any(item == "dif" for item in parciais):
            token = "DIVERGÊNCIA"
        elif operacao in {"apresentar", "diferenca_informada"}:
            token = "INFORMADO"
        elif operacao in {"diferenca", "diferenca_preco"}:
            token = "SEM DIVERGÊNCIA"
        else:
            token = "COMPATÍVEL"
        if any(item == "NÃO VERIFICÁVEL" for item in parciais) and token not in {"DIVERGÊNCIA"}:
            return _insuficiente("Parte dos itens não tem os dois valores. A lacuna não foi tratada como divergência.")
        return _resultado(token, calculos=calculos)


class ExecutorContrapartida(ExecutorRegraBase):
    nome = "contrapartida"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        contrapartidas = list(contexto.prestacao.contrapartidas.all())
        if operacao == "existencia":
            if contrapartidas:
                return _resultado(
                    "EXISTE",
                    referencias=[referencia(tipo_fonte="contrapartida", identificador=item.id, campo="descricao", valor_utilizado=item.descricao[:255], papel_na_regra="contrapartida") for item in contrapartidas],
                )
            if contexto.instrumento() is None:
                return _insuficiente("Instrumento ausente. Contrapartida não foi presumida.")
            return _insuficiente("Não há contrapartida estruturada. A ausência do registro não foi tratada como inexistência comprovada.")
        if operacao == "financeira":
            from aplicacao.regras.contexto import normalizar

            financeiras = [item for item in contrapartidas if "financeir" in normalizar(item.descricao)]
            if not financeiras:
                return _resultado("", "A contrapartida localizada não está identificada como financeira.", status=StatusTecnico.NAO_APLICAVEL)
            creditos = [item for item in contexto.movimentacoes() if item.tipo == "credito"]
            if not creditos:
                return _insuficiente("Contrapartida financeira indicada, sem crédito estruturado no extrato.")
            return _resultado("IDENTIFICADO", "Crédito estruturado localizado. A origem do aporte deve ser validada pelo analista.")
        if not contrapartidas:
            return _insuficiente("Sem contrapartida estruturada não há evidência a localizar.")
        return _resultado("EVIDÊNCIA LOCALIZADA" if operacao == "evidencia" else "EVIDÊNCIA LOCALIZADA")


class ExecutorDevolucao(ExecutorRegraBase):
    nome = "devolucao"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        saldo = contexto.saldo_estruturado()
        devolucoes = list(contexto.prestacao.devolucoes.all())
        total_devolvido = somar_de(dinheiro(item.valor) for item in devolucoes)
        if saldo is None:
            return _insuficiente("Extrato estruturado insuficiente para apurar saldo. Nenhum saldo foi presumido.")
        calculos = [calculo("saldo", {"creditos_menos_debitos": saldo}, saldo, "BRL")]
        if operacao == "saldo":
            return _resultado("SALDO IDENTIFICADO", "Saldo calculado só sobre lançamentos estruturados.", calculos=calculos)
        if total_devolvido is None:
            return _insuficiente("Há saldo estruturado, mas não há valor de devolução para comparar. A ausência não foi tratada como saldo não devolvido.")
        calculos.append(calculo("devolucao", {"saldo": saldo, "devolvido": total_devolvido}, saldo - total_devolvido, "BRL"))
        if operacao == "credito" and saldo <= ZERO:
            return _resultado("NÃO IDENTIFICADA", "O saldo estruturado não é positivo.", calculos=calculos)
        if saldo <= ZERO or total_devolvido >= saldo:
            token = "DEVOLVIDO" if operacao == "saldo_devolvido" else "IDENTIFICADA"
            return _resultado(token, calculos=calculos)
        token = "POSSÍVEL SALDO NÃO DEVOLVIDO" if operacao == "saldo_devolvido" else "IDENTIFICADA"
        return _resultado(token, "A diferença numérica não é conclusão jurídica.", calculos=calculos, status=StatusTecnico.ATENCAO)


class ExecutorGovernanca(ExecutorRegraBase):
    nome = "governanca"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        operacao = regra.configuracao.get("operacao")
        if operacao == "nao_conclusivo":
            return _resultado("NÃO CONCLUSIVO", REGRA_DE_OURO)
        if operacao == "validacao_humana":
            return _resultado("PENDENTE DE VALIDAÇÃO", "O resultado permanece pendente de validação humana.")
        violacoes = []
        for codigo, resultado in contexto.resultados.items():
            if resultado.entradas.get("dados_insuficientes") and resultado.status_tecnico == StatusTecnico.DIVERGENCIA:
                violacoes.append(codigo)
            if resultado.resultado_funcional.strip().upper() in {"REGULAR", "IRREGULAR", "APROVADO", "REPROVADO"}:
                violacoes.append(codigo)
        if violacoes:
            return _resultado("NÃO VERIFICÁVEL", "Houve tratamento de ausência como divergência ou conclusão vedada: " + ", ".join(violacoes), status=StatusTecnico.ERRO)
        return _resultado("NÃO VERIFICÁVEL", "Ausência de informação nesta rodada não foi registrada como divergência.")


class ExecutorSemantico(ExecutorRegraBase):
    nome = "semantico"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        refs = contexto.referencias_documentos(contexto.documentos, "contexto_semantico")
        return _resultado(
            RESULTADO_SEMANTICO,
            "A execução semântica fica para a onda seguinte. Nenhum resultado conclusivo foi produzido por heurística.",
            referencias=refs,
            encaminhamento=Encaminhamento.REQUER_IA,
            status=StatusTecnico.NAO_EXECUTADA,
            entradas={"fontes_autorizadas": [documento.id for documento in contexto.documentos]},
        )


class ExecutorAnalista(ExecutorRegraBase):
    nome = "analista"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        limitacao = "Não há fonte estruturada de dirigentes ou de vínculo familiar. Parentesco não é inferido pelo sobrenome."
        return _resultado(
            "NÃO VERIFICÁVEL",
            limitacao,
            encaminhamento=Encaminhamento.REQUER_ANALISTA,
            status=StatusTecnico.INCONCLUSIVO,
            entradas={"dados_insuficientes": True, "metodo": "nao_inferido"},
        )


class ExecutorForaEscopo(ExecutorRegraBase):
    nome = "fora_escopo"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        return _resultado(regra.resultados_possiveis, regra.limitacao_observacao, status=StatusTecnico.NAO_EXECUTADA)


class ExecutorAchado(ExecutorRegraBase):
    nome = "achado"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        candidatos = []
        for codigo, resultado in contexto.resultados.items():
            if codigo.startswith("ACH-") or codigo.startswith("SYS-"):
                continue
            if resultado.status_tecnico not in {StatusTecnico.DIVERGENCIA, StatusTecnico.ATENCAO}:
                continue
            candidatos.append((codigo, resultado))
        if regra.configuracao.get("operacao") == "rastreavel":
            completos = [codigo for codigo, resultado in candidatos if resultado.resultado_funcional and resultado.referencias]
            if completos:
                return _resultado("ACHADO RASTREÁVEL", "Há elementos para um achado futuro. Nenhum achado foi gravado.", entradas={"regras": completos})
            return _resultado("NÃO GERAR", "Não há fato, evidência e origem suficientes para um achado futuro.", status=StatusTecnico.INCONCLUSIVO)
        resolucao = contexto.resolucao_normativa()
        if candidatos and resolucao is not None and resolucao.elegiveis:
            return _resultado(
                "FUNDAMENTADO",
                "O fundamento usa somente normas elegíveis na data de referência. Nenhum achado foi gravado.",
                referencias=contexto.referencias_normativas(),
                entradas={"regras": [codigo for codigo, _resultado_item in candidatos]},
            )
        if candidatos:
            return _resultado("INSUFICIENTE", "Há situação a examinar, sem norma elegível vinculada. Nenhum fundamento foi inventado.", status=StatusTecnico.INCONCLUSIVO)
        return _resultado("INSUFICIENTE", "Não há situação com evidência bastante para fundamentar apontamento.", status=StatusTecnico.INCONCLUSIVO)


class ExecutorNotaFiscal(ExecutorRegraBase):
    nome = "nota_fiscal"

    def executar(self, regra, contexto) -> ResultadoExecutor:
        fiscais = list(contexto.prestacao.documentos_fiscais.select_related("emitente__entidade"))
        if not fiscais:
            return _insuficiente("Não há nota fiscal estruturada. Nenhuma consulta externa foi realizada.")
        completas = []
        for fiscal in fiscais:
            cnpj = digitos_entidade(getattr(fiscal.emitente, "entidade", None))
            if fiscal.numero and fiscal.data_emissao and fiscal.valor is not None and cnpj:
                completas.append(fiscal)
        if not completas:
            return _resultado("NÃO VALIDÁVEL", "Faltam chave, número, CNPJ, data ou valor para uma consulta externa. Nenhuma consulta foi feita.", status=StatusTecnico.INCONCLUSIVO)
        return _resultado(
            "VALIDÁVEL",
            "Os dados permitem avaliação externa. Esta onda não consulta portal.",
            referencias=[referencia(tipo_fonte="documento_fiscal", identificador=fiscal.id, campo="numero", valor_utilizado=fiscal.numero, papel_na_regra="nota_fiscal") for fiscal in completas],
        )


EXECUTORES = {
    executor.nome: executor
    for executor in (
        ExecutorContexto(),
        ExecutorDocumental(),
        ExecutorTesteCego(),
        ExecutorComparacaoValor(),
        ExecutorSomatorio(),
        ExecutorComparacaoData(),
        ExecutorCorrespondenciaIdentidade(),
        ExecutorMovimentacaoBancaria(),
        ExecutorPlanoTrabalho(),
        ExecutorContrapartida(),
        ExecutorDevolucao(),
        ExecutorGovernanca(),
        ExecutorSemantico(),
        ExecutorAnalista(),
        ExecutorForaEscopo(),
        ExecutorAchado(),
        ExecutorNotaFiscal(),
    )
}
