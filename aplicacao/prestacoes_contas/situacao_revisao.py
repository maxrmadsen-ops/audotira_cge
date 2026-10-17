"""Rótulos de revisão. Não grava e não troca o estado já persistido."""

from decimal import Decimal, ROUND_HALF_UP

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.prestacoes_contas.escolhas import StatusRevisaoPlano

ROTULOS = {
    StatusRevisaoPlano.AGUARDANDO: "Pendente de revisão inicial",
    StatusRevisaoPlano.CONFIRMADO: "Confirmado por usuário autorizado",
    StatusRevisaoPlano.CORRIGIDO: "Corrigido",
    StatusRevisaoPlano.REJEITADO: "Não correspondente",
}
ROTULO_RATIFICACAO = "Pendente de ratificação de decisão importada"


def chaves_ratificacao(prestacao) -> set[tuple]:
    """Decisões importadas que continuam pendentes. A leitura não altera o registro."""

    chaves = set()
    eventos = RegistroAuditoria.objects.filter(
        evento=RegistroAuditoria.Evento.VALIDACAO_HUMANA,
        detalhes__prestacao=prestacao.numero_processo,
        detalhes__status_destino=StatusRevisaoPlano.AGUARDANDO,
    )
    for evento in eventos:
        for item in evento.detalhes.get("pendencias") or []:
            chaves.add(_chave(item.get("tipo") or "", item.get("ordem"), item.get("pagina"), item.get("descricao") or ""))
    return chaves


def rotulo_revisao(objeto, tipo: str, chaves: set[tuple] | None = None) -> str:
    chaves = chaves or set()
    if objeto.status_revisao == StatusRevisaoPlano.AGUARDANDO and _pendente_ratificacao(objeto, tipo, chaves):
        return ROTULO_RATIFICACAO
    base = ROTULOS.get(objeto.status_revisao, "Não identificado")
    if tipo == "item" and objeto.status_revisao == StatusRevisaoPlano.AGUARDANDO:
        if divergencia_aritmetica(objeto):
            return f"{base} · Divergente ou não conclusivo"
        if not objeto.pagina or not (objeto.trecho or "").strip():
            return f"{base} · Informação ausente"
    return base


def _pendente_ratificacao(objeto, tipo: str, chaves: set[tuple]) -> bool:
    if tipo in {"identificacao", "cronograma"}:
        return (tipo, None, None, "") in chaves
    return _combina(objeto, tipo, chaves)


def divergencia_aritmetica(item) -> bool:
    if item.quantidade is None or item.valor_unitario is None or item.valor_previsto is None:
        return False
    esperado = (Decimal(item.quantidade) * Decimal(item.valor_unitario)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return esperado != Decimal(item.valor_previsto)


def avaliar_lote(item, chaves: set[tuple]) -> tuple[bool, str]:
    """Diz se o item pode entrar numa confirmação em lote. Não grava."""

    if item.status_revisao == StatusRevisaoPlano.REJEITADO:
        return False, "Item marcado como não correspondente."
    if item.status_revisao != StatusRevisaoPlano.AGUARDANDO:
        return False, "Já possui decisão de revisão."
    if _combina(item, "item", chaves):
        return False, "Decisão importada exige ratificação individual."
    if not item.pagina or not (item.trecho or "").strip():
        return False, "Sem evidência de página ou trecho. A ausência não é irregularidade."
    if divergencia_aritmetica(item):
        return False, "Divergência entre quantidade, valor unitário e total."
    return True, ""


def _combina(objeto, tipo: str, chaves: set[tuple]) -> bool:
    return _chave(tipo, getattr(objeto, "ordem", None), objeto.pagina, objeto.descricao) in chaves


def _chave(tipo: str, ordem, pagina, descricao: str) -> tuple:
    return (tipo or "", ordem, pagina, (descricao or "")[:120])
