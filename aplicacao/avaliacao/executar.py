import re

from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.avaliacao.comparacao import comparar_regras, resumir_regras
from aplicacao.avaliacao.comparador import comparar_achados
from aplicacao.avaliacao.escolhas import CRITICAS, ClassificacaoCorrespondencia, StatusAvaliacao, StatusGroundTruth
from aplicacao.avaliacao.excecoes import ErroAvaliacao
from aplicacao.avaliacao.hash_conteudo import calcular_hash_avaliacao
from aplicacao.avaliacao.metricas import contar_correspondencias, materialidade_falsos_negativos, serializar
from aplicacao.avaliacao.models import AvaliacaoInteligenciaArtificial
from aplicacao.avaliacao.permissoes import pode_concluir_avaliacao, pode_revisar_correspondencia
from aplicacao.avaliacao.snapshot import criar_snapshot
from aplicacao.pareceres.escolhas import StatusPreAnalise, StatusValidacaoAfirmacao, TipoAfirmacao

TIPOS_MATERIAIS = {
    TipoAfirmacao.FATO,
    TipoAfirmacao.CALCULO,
    TipoAfirmacao.ACHADO,
    TipoAfirmacao.CONSTATACAO_POSITIVA,
    TipoAfirmacao.FUNDAMENTACAO,
}
MOTIVOS = (
    ("fonte inexistente", "fonte_inexistente"),
    ("valor", "valor_divergente"),
    ("página", "valor_divergente"),
    ("pagina", "valor_divergente"),
    ("código ausente", "referencia_inventada"),
    ("codigo ausente", "referencia_inventada"),
    ("regra inexistente", "regra_inexistente"),
    ("norma fora", "norma_fora_vigencia"),
    ("norma inexistente", "norma_inexistente"),
    ("documento inexistente", "documento_inexistente"),
    ("referência inventada", "referencia_inventada"),
    ("referencia inventada", "referencia_inventada"),
    ("outra prestação", "referencia_inventada"),
)
VEDADA = re.compile(r"\b(APROVAD[OA]|REPROVAD[OA])\b|\bJULGAR_IRREGULAR\b|\bJULGAR_REGULAR\b", re.IGNORECASE)


def _codigo() -> str:
    numeros = []
    for codigo in AvaliacaoInteligenciaArtificial.objects.values_list("codigo", flat=True).distinct():
        if codigo.startswith("AV-") and codigo[3:].isdigit():
            numeros.append(int(codigo[3:]))
    return f"AV-{(max(numeros) if numeros else 0) + 1:06d}"


def _auditar(usuario, acao, avaliacao, extra=None):
    registrar_evento(
        evento=RegistroAuditoria.Evento.AVALIACAO_IA,
        descricao=f"Avaliação: {acao}.",
        usuario=usuario,
        detalhes={"codigo": avaliacao.codigo, "versao": avaliacao.versao, "acao": acao, **(extra or {})},
    )


def criar_avaliacao(pre_analise, ground_truth, usuario, demonstracao=False):
    if not pode_concluir_avaliacao(usuario):
        raise ErroAvaliacao("Somente o auditor pode iniciar a avaliação oficial.")
    if pre_analise.status != StatusPreAnalise.CONGELADA:
        raise ErroAvaliacao("A avaliação oficial exige pré-análise congelada.")
    if ground_truth.prestacao_contas_id != pre_analise.prestacao_contas_id:
        raise ErroAvaliacao("O Ground Truth pertence a outra prestação.")
    status = StatusAvaliacao.PREPARANDO if ground_truth.status == StatusGroundTruth.CONGELADO else StatusAvaliacao.AGUARDANDO_GROUND_TRUTH
    snapshot = criar_snapshot(pre_analise) if status == StatusAvaliacao.PREPARANDO else None
    avaliacao = AvaliacaoInteligenciaArtificial.objects.create(
        codigo=_codigo(),
        prestacao_contas=pre_analise.prestacao_contas,
        snapshot=snapshot,
        ground_truth=ground_truth,
        status=status,
        iniciado_por=usuario,
        dados_demonstracao=demonstracao or ground_truth.dados_demonstracao,
    )
    _auditar(usuario, "inicio", avaliacao)
    if snapshot is not None:
        _auditar(usuario, "snapshot", avaliacao, {"snapshot": snapshot.pk, "hash": snapshot.hash_conteudo})
    return avaliacao


def _motivo(texto: str) -> str | None:
    bruto = (texto or "").strip().casefold()
    if not bruto:
        return None
    for prefixo, codigo in MOTIVOS:
        if prefixo in bruto:
            return codigo
    return "outro"


def medir_proveniencia(pre_analise) -> dict:
    afirmacoes = []
    for secao in pre_analise.secoes.prefetch_related("afirmacoes"):
        afirmacoes.extend(secao.afirmacoes.all())
    materiais = [item for item in afirmacoes if item.tipo in TIPOS_MATERIAIS]
    if not materiais:
        return {
            "produzidas": 0,
            "suportadas": 0,
            "parciais": 0,
            "nao_suportadas": 0,
            "rejeitadas": 0,
            "taxa_suportadas": None,
            "taxa_rejeicao": None,
            "motivos": {},
        }
    suportadas = sum(1 for item in materiais if item.status_validacao == StatusValidacaoAfirmacao.VALIDADA)
    parciais = sum(1 for item in materiais if item.status_validacao == StatusValidacaoAfirmacao.PARCIALMENTE_SUPORTADA)
    nao = sum(1 for item in materiais if item.status_validacao == StatusValidacaoAfirmacao.NAO_SUPORTADA)
    rejeitadas = sum(1 for item in materiais if item.status_validacao == StatusValidacaoAfirmacao.REJEITADA)
    motivos = {}
    for item in materiais:
        if item.status_validacao != StatusValidacaoAfirmacao.REJEITADA:
            continue
        codigo = _motivo(item.motivo_rejeicao)
        if codigo is None:
            continue
        motivos[codigo] = motivos.get(codigo, 0) + 1
    from decimal import Decimal, ROUND_HALF_UP

    def taxa(parte):
        return format((Decimal(parte) / Decimal(len(materiais))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")

    return {
        "produzidas": len(materiais),
        "suportadas": suportadas,
        "parciais": parciais,
        "nao_suportadas": nao,
        "rejeitadas": rejeitadas,
        "taxa_suportadas": taxa(suportadas),
        "taxa_rejeicao": taxa(rejeitadas),
        "motivos": motivos,
    }


def medir_pre_analise(pre_analise, correspondencias, execucoes) -> dict:
    textos = f"{pre_analise.resumo_executivo}\n{pre_analise.escopo}\n{pre_analise.limitacoes}"
    tem_limitacao = any((item.limitacao or "").strip() for item in execucoes)
    contradiz = False
    for item in correspondencias:
        if item.achado_id and item.achado.vinculos_evidencia.filter(papel="contradiz").exists():
            contradiz = True
            break
    preserva_contraditorio = None
    if contradiz:
        preserva_contraditorio = "contrad" in textos.casefold()
    return {
        "achados_presentes": sum(1 for item in correspondencias if item.classificacao == ClassificacaoCorrespondencia.VERDADEIRO_POSITIVO),
        "achados_omitidos": sum(1 for item in correspondencias if item.classificacao == ClassificacaoCorrespondencia.FALSO_NEGATIVO),
        "limitacoes_preservadas": bool(pre_analise.limitacoes.strip()) if tem_limitacao else None,
        "contraditorios_preservados": preserva_contraditorio,
        "conclusao_administrativa_vedada": bool(VEDADA.search(textos)),
        "encaminhamento_registrado": bool(pre_analise.encaminhamento),
    }


def _metricas(avaliacao, correspondencias, comparacoes, execucoes):
    classificacao = contar_correspondencias(correspondencias)
    materialidade = materialidade_falsos_negativos(correspondencias)
    regras = resumir_regras(comparacoes)
    fn_criticidade = {"baixa": 0, "media": 0, "alta": 0, "critica": 0}
    for item in correspondencias:
        if item.classificacao != ClassificacaoCorrespondencia.FALSO_NEGATIVO or item.ground_truth_achado_id is None:
            continue
        fn_criticidade[item.ground_truth_achado.criticidade] = fn_criticidade.get(item.ground_truth_achado.criticidade, 0) + 1
    modelo = None
    if avaliacao.snapshot_id:
        modelo = avaliacao.snapshot.referencias.get("modelo")
    return serializar(
        {
            "tp": classificacao["tp"],
            "fp": classificacao["fp"],
            "fn": classificacao["fn"],
            "parciais": classificacao["parciais"],
            "pendentes": classificacao["pendentes"],
            "precisao": classificacao["precisao"],
            "recall": classificacao["recall"],
            "f1": classificacao["f1"],
            "regras": regras,
            "materialidade_fn": materialidade,
            "fn_por_criticidade": fn_criticidade,
            "fn_criticos": fn_criticidade["alta"] + fn_criticidade["critica"],
            "proveniencia": medir_proveniencia(avaliacao.snapshot.pre_analise),
            "pre_analise": medir_pre_analise(avaliacao.snapshot.pre_analise, correspondencias, execucoes),
            "modelo": modelo,
            "modo": avaliacao.ground_truth.modo,
        }
    )


def executar_comparacao(avaliacao, usuario=None):
    if avaliacao.status == StatusAvaliacao.CONGELADA:
        raise ErroAvaliacao("Avaliação congelada não pode ser alterada.")
    if avaliacao.ground_truth.status != StatusGroundTruth.CONGELADO:
        avaliacao.status = StatusAvaliacao.AGUARDANDO_GROUND_TRUTH
        avaliacao.save(update_fields=["status", "atualizado_em"])
        raise ErroAvaliacao("A avaliação oficial exige Ground Truth congelado.")
    if avaliacao.snapshot_id is None or avaliacao.snapshot.pre_analise.status != StatusPreAnalise.CONGELADA:
        raise ErroAvaliacao("A avaliação oficial exige pré-análise congelada.")
    try:
        with transaction.atomic():
            avaliacao.status = StatusAvaliacao.COMPARANDO
            avaliacao.erro = ""
            avaliacao.save(update_fields=["status", "erro", "atualizado_em"])
            avaliacao.comparacoes_regra.all().delete()
            avaliacao.correspondencias.all().delete()
            analise = avaliacao.snapshot.execucao_analise
            execucoes = list(analise.execucoes.select_related("regra"))
            comparar_regras(avaliacao, execucoes, avaliacao.ground_truth.regras_referencia.select_related("regra"))
            comparar_achados(
                avaliacao,
                list(analise.achados.prefetch_related("vinculos_regra", "vinculos_evidencia", "fundamentacoes", "pessoas", "despesas", "pagamentos")),
                list(avaliacao.ground_truth.achados_referencia.prefetch_related("regras", "evidencias", "documentos", "normas", "pessoas", "despesas", "pagamentos")),
            )
            correspondencias = list(avaliacao.correspondencias.select_related("ground_truth_achado", "achado"))
            comparacoes = list(avaliacao.comparacoes_regra.select_related("regra"))
            avaliacao.metricas = _metricas(avaliacao, correspondencias, comparacoes, execucoes)
            pendente = any(item.classificacao == ClassificacaoCorrespondencia.PENDENTE_REVISAO for item in correspondencias)
            avaliacao.status = StatusAvaliacao.AGUARDANDO_REVISAO if pendente else StatusAvaliacao.CONCLUIDA
            if avaliacao.status == StatusAvaliacao.CONCLUIDA:
                avaliacao.concluido_em = timezone.now()
            avaliacao.versao_registro += 1
            avaliacao.save()
    except ErroAvaliacao:
        raise
    except Exception:
        avaliacao.status = StatusAvaliacao.ERRO
        avaliacao.erro = "Falha controlada na comparação."
        avaliacao.save(update_fields=["status", "erro", "atualizado_em"])
        _auditar(usuario, "erro", avaliacao)
        raise ErroAvaliacao("Falha controlada na comparação.")
    _auditar(usuario, "matching", avaliacao)
    _auditar(usuario, "metricas", avaliacao, {"modo": avaliacao.ground_truth.modo})
    return avaliacao


def concluir(avaliacao, usuario):
    if not pode_concluir_avaliacao(usuario):
        raise ErroAvaliacao("Somente o auditor pode concluir a avaliação.")
    if avaliacao.status == StatusAvaliacao.CONGELADA:
        raise ErroAvaliacao("Avaliação congelada não pode ser alterada.")
    if avaliacao.correspondencias.filter(classificacao=ClassificacaoCorrespondencia.PENDENTE_REVISAO).exists():
        raise ErroAvaliacao("Há correspondência pendente de revisão.")
    avaliacao.status = StatusAvaliacao.CONCLUIDA
    avaliacao.concluido_em = timezone.now()
    avaliacao.revisado_por = usuario
    avaliacao.save(update_fields=["status", "concluido_em", "revisado_por", "atualizado_em"])
    _auditar(usuario, "conclusao", avaliacao)
    return avaliacao


def congelar_avaliacao(avaliacao, usuario):
    if not pode_concluir_avaliacao(usuario):
        raise ErroAvaliacao("Somente o auditor pode congelar a avaliação. Permissão administrativa não equivale a autoridade técnica.")
    if avaliacao.status == StatusAvaliacao.CONGELADA:
        raise ErroAvaliacao("Avaliação congelada não pode ser alterada.")
    if avaliacao.status != StatusAvaliacao.CONCLUIDA:
        raise ErroAvaliacao("Somente avaliação concluída pode ser congelada.")
    if avaliacao.correspondencias.filter(classificacao=ClassificacaoCorrespondencia.PENDENTE_REVISAO).exists():
        raise ErroAvaliacao("Há correspondência pendente de revisão.")
    avaliacao.hash_conteudo = calcular_hash_avaliacao(avaliacao)
    avaliacao.status = StatusAvaliacao.CONGELADA
    avaliacao.congelado_por = usuario
    avaliacao.congelado_em = timezone.now()
    avaliacao.versao_registro += 1
    avaliacao.save()
    _auditar(usuario, "congelamento", avaliacao)
    return avaliacao


def nova_versao_avaliacao(avaliacao, ground_truth, usuario):
    if not pode_concluir_avaliacao(usuario):
        raise ErroAvaliacao("Somente o auditor pode versionar a avaliação.")
    if avaliacao.status != StatusAvaliacao.CONGELADA:
        raise ErroAvaliacao("A nova versão parte de uma avaliação congelada.")
    if ground_truth.status != StatusGroundTruth.CONGELADO:
        raise ErroAvaliacao("A nova versão exige Ground Truth congelado.")
    snapshot = criar_snapshot(avaliacao.snapshot.pre_analise)
    nova = AvaliacaoInteligenciaArtificial.objects.create(
        codigo=avaliacao.codigo,
        prestacao_contas=avaliacao.prestacao_contas,
        snapshot=snapshot,
        ground_truth=ground_truth,
        avaliacao_anterior=avaliacao,
        versao=avaliacao.versao + 1,
        iniciado_por=usuario,
        dados_demonstracao=avaliacao.dados_demonstracao,
    )
    _auditar(usuario, "nova_versao", nova, {"origem": avaliacao.versao})
    return nova


def criticos(correspondencias):
    return [
        item
        for item in correspondencias
        if item.classificacao == ClassificacaoCorrespondencia.FALSO_NEGATIVO
        and item.ground_truth_achado_id
        and item.ground_truth_achado.criticidade in CRITICAS
    ]
