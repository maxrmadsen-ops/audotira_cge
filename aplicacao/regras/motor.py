from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.regras.catalogo import hash_catalogo, validar_grafo
from aplicacao.regras.contexto import ContextoExecucao
from aplicacao.regras.escolhas import (
    Encaminhamento,
    EtapaAnalise,
    SINTESE_NAO_CONCLUSIVA,
    StatusAnalise,
    StatusTecnico,
    TipoDependencia,
)
from aplicacao.regras.executores import EXECUTORES
from aplicacao.regras.models import CalculoExecucaoRegra, ExecucaoAnalise, ExecucaoRegra, ReferenciaExecucao, RegraAnalise
from aplicacao.regras.resultados import ResultadoExecutor, conclusao_vedada


def ordenar_regras(regras: list[RegraAnalise]) -> list[RegraAnalise]:
    por_codigo = {regra.codigo: regra for regra in regras}
    dependencias = {regra.codigo: [item.codigo_requisito for item in regra.dependencias.all()] for regra in regras}
    validar_grafo(dependencias)
    visitados: set[str] = set()
    saida: list[str] = []

    def visitar(codigo: str) -> None:
        if codigo in visitados:
            return
        visitados.add(codigo)
        for requisito in dependencias.get(codigo, []):
            if requisito in por_codigo:
                visitar(requisito)
        saida.append(codigo)

    for regra in regras:
        visitar(regra.codigo)
    return [por_codigo[codigo] for codigo in saida]


def _dependencia_bloqueia(regra: RegraAnalise, contexto: ContextoExecucao) -> ResultadoExecutor | None:
    for dependencia in regra.dependencias.all():
        anterior = contexto.resultados.get(dependencia.codigo_requisito)
        esperado = (dependencia.parametro or {}).get("resultado_contem", "")
        if dependencia.tipo in {TipoDependencia.CONDICIONA, TipoDependencia.REQUER_RESULTADO}:
            if anterior is None or (esperado and esperado not in anterior.resultado_funcional):
                return ResultadoExecutor(
                    "",
                    StatusTecnico.NAO_APLICAVEL,
                    f"Depende de {dependencia.codigo_requisito} com resultado contendo «{esperado}».",
                )
        elif dependencia.tipo == TipoDependencia.REQUER_SUCESSO:
            if anterior is None or anterior.status_tecnico != StatusTecnico.SUCESSO:
                return ResultadoExecutor("", StatusTecnico.NAO_APLICAVEL, f"Depende do sucesso de {dependencia.codigo_requisito}.")
        elif dependencia.tipo == TipoDependencia.BLOQUEIA and anterior is not None and anterior.status_tecnico == StatusTecnico.SUCESSO:
            return ResultadoExecutor("", StatusTecnico.NAO_APLICAVEL, f"Bloqueada por {dependencia.codigo_requisito}.")
    return None


def _snapshot(regra: RegraAnalise) -> dict:
    return {
        "codigo": regra.codigo,
        "versao": regra.versao,
        "categoria": regra.categoria,
        "titulo": regra.titulo,
        "descricao_original": regra.descricao_original,
        "fonte_normativa_original": regra.fonte_normativa_original,
        "aplicabilidade_original": regra.aplicabilidade_original,
        "entradas_necessarias": regra.entradas_necessarias,
        "dados_extrair": regra.dados_extrair,
        "logica_verificacao": regra.logica_verificacao,
        "resultados_possiveis": regra.resultados_possiveis,
        "evidencia_obrigatoria": regra.evidencia_obrigatoria,
        "limitacao_observacao": regra.limitacao_observacao,
        "tratamento_analista": regra.tratamento_analista,
        "tipo_execucao": regra.tipo_execucao,
        "capacidade": regra.capacidade,
        "executor": regra.executor,
    }


class MotorRegras:
    """Executa o catálogo ativo. Não emite conclusão administrativa da prestação."""

    def executar(self, analise: ExecucaoAnalise) -> ExecucaoAnalise:
        if analise.status != StatusAnalise.EM_ANDAMENTO:
            return analise
        analise.iniciada_em = timezone.now()
        analise.versao_catalogo = analise.versao_catalogo or hash_catalogo()
        analise.sintese = SINTESE_NAO_CONCLUSIVA
        analise.etapa = EtapaAnalise.PREPARANDO_CONTEXTO
        analise.save()
        try:
            contexto = ContextoExecucao.montar(analise.prestacao_contas, analise.modo_teste_cego)
            contexto.analise = analise
            analise.documentos_excluidos = contexto.excluidos
            analise.etapa = EtapaAnalise.VERIFICANDO_APLICABILIDADE
            analise.save(update_fields=["documentos_excluidos", "etapa"])
            regras = ordenar_regras(list(RegraAnalise.objects.filter(ativa=True).prefetch_related("dependencias").order_by("ordem", "codigo")))
            analise.etapa = EtapaAnalise.RESOLVENDO_NORMAS
            analise.save(update_fields=["etapa"])
            analise.etapa = EtapaAnalise.EXECUTANDO_REGRAS
            analise.save(update_fields=["etapa"])
            for ordem, regra in enumerate(regras, start=1):
                resultado = self._executar_regra(regra, contexto)
                contexto.resultados[regra.codigo] = resultado
                self._gravar(analise, regra, resultado, ordem)
            self._totalizar(analise)
        except Exception as erro:
            analise.status = StatusAnalise.ERRO
            analise.etapa = EtapaAnalise.ERRO
            analise.erro = str(erro)[:1000]
            analise.finalizada_em = timezone.now()
            analise.sintese = SINTESE_NAO_CONCLUSIVA
            analise.save()
            raise
        return analise

    def _executar_regra(self, regra: RegraAnalise, contexto: ContextoExecucao) -> ResultadoExecutor:
        bloqueio = _dependencia_bloqueia(regra, contexto)
        if bloqueio is not None:
            return bloqueio
        executor = EXECUTORES.get(regra.executor)
        if executor is None:
            return ResultadoExecutor("", StatusTecnico.ERRO, f"Executor {regra.executor} não está registrado.")
        try:
            resultado = executor.executar(regra, contexto)
        except Exception as erro:
            return ResultadoExecutor("", StatusTecnico.ERRO, f"Falha isolada em {regra.codigo}: {erro}"[:500])
        if conclusao_vedada(resultado.resultado_funcional):
            return ResultadoExecutor(
                SINTESE_NAO_CONCLUSIVA,
                StatusTecnico.ERRO,
                "O motor bloqueou uma conclusão administrativa. A decisão permanece com o analista.",
            )
        return resultado

    def _gravar(self, analise, regra, resultado: ResultadoExecutor, ordem: int) -> None:
        execucao = ExecucaoRegra.objects.create(
            analise=analise,
            regra=regra,
            snapshot=_snapshot(regra),
            resultado_funcional=(resultado.resultado_funcional or "")[:120],
            status_tecnico=resultado.status_tecnico,
            encaminhamento=resultado.encaminhamento or Encaminhamento.NENHUM,
            limitacao=resultado.limitacao or "",
            entradas=resultado.entradas or {},
            ordem=ordem,
        )
        for item in resultado.referencias:
            ReferenciaExecucao.objects.create(
                execucao=execucao,
                tipo_fonte=item.get("tipo_fonte", "")[:40],
                identificador=str(item.get("identificador") or "")[:80],
                documento_id=item.get("documento_id"),
                pagina_id=item.get("pagina_id"),
                trecho_normativo_id=item.get("trecho_normativo_id"),
                trecho=(item.get("trecho") or "")[:500],
                campo=(item.get("campo") or "")[:80],
                valor_utilizado=str(item.get("valor_utilizado") or "")[:255],
                papel_na_regra=(item.get("papel_na_regra") or "")[:80],
            )
        for item in resultado.calculos:
            try:
                valor = Decimal(str(item["resultado"]))
            except (InvalidOperation, KeyError):
                continue
            CalculoExecucaoRegra.objects.create(
                execucao=execucao,
                operacao=item.get("operacao", "")[:80],
                operandos=item.get("operandos") or {},
                resultado=valor,
                unidade=(item.get("unidade") or "")[:20],
            )
        usos = (resultado.entradas or {}).get("usos") or []
        if usos:
            from aplicacao.inteligencia_artificial.integracao import vincular_usos

            vincular_usos(execucao, usos)

    def _totalizar(self, analise: ExecucaoAnalise) -> None:
        execucoes = analise.execucoes.all()
        analise.total_regras = execucoes.count()
        analise.nao_aplicaveis = execucoes.filter(status_tecnico=StatusTecnico.NAO_APLICAVEL).count()
        analise.erros = execucoes.filter(status_tecnico=StatusTecnico.ERRO).count()
        analise.requer_ia = execucoes.filter(encaminhamento=Encaminhamento.REQUER_IA).count()
        analise.requer_analista = execucoes.filter(encaminhamento=Encaminhamento.REQUER_ANALISTA).count()
        analise.nao_verificaveis = execucoes.filter(resultado_funcional="NÃO VERIFICÁVEL").count()
        analise.executadas = execucoes.exclude(
            status_tecnico__in=[StatusTecnico.NAO_APLICAVEL, StatusTecnico.NAO_EXECUTADA, StatusTecnico.ERRO]
        ).count()
        analise.etapa = EtapaAnalise.REGISTRANDO_CALCULOS
        analise.etapa = EtapaAnalise.REGISTRANDO_LIMITACOES
        analise.etapa = EtapaAnalise.AGUARDANDO_VALIDACAO
        analise.status = StatusAnalise.AGUARDANDO_VALIDACAO
        analise.sintese = SINTESE_NAO_CONCLUSIVA
        analise.finalizada_em = timezone.now()
        analise.save()
        registrar_evento(
            evento=RegistroAuditoria.Evento.EXECUCAO_REGRA,
            descricao=f"Análise {analise.pk} aguardando validação humana.",
            usuario=analise.criado_por,
            detalhes={
                "analise": analise.pk,
                "prestacao": analise.prestacao_contas_id,
                "modo_teste_cego": analise.modo_teste_cego,
                "total_regras": analise.total_regras,
                "erros": analise.erros,
            },
        )


def criar_analise(*, prestacao, usuario, modo_teste_cego: bool) -> ExecucaoAnalise:
    from aplicacao.regras.escolhas import ModoExecucao

    return ExecucaoAnalise.objects.create(
        prestacao_contas=prestacao,
        versao_catalogo=hash_catalogo(),
        modo_execucao=ModoExecucao.TESTE_CEGO if modo_teste_cego else ModoExecucao.NORMAL,
        modo_teste_cego=modo_teste_cego,
        status=StatusAnalise.EM_ANDAMENTO,
        etapa=EtapaAnalise.PREPARANDO_CONTEXTO,
        sintese=SINTESE_NAO_CONCLUSIVA,
        criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
    )


def executar_analise(analise_id: int) -> None:
    with transaction.atomic():
        analise = ExecucaoAnalise.objects.select_for_update().get(pk=analise_id)
        MotorRegras().executar(analise)
