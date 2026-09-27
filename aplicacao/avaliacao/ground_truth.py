from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.avaliacao.escolhas import StatusGroundTruth
from aplicacao.avaliacao.excecoes import ErroAvaliacao, ErroConcorrencia
from aplicacao.avaliacao.hash_conteudo import calcular_hash_ground_truth
from aplicacao.avaliacao.models import GroundTruthAchado, GroundTruthPrestacao, GroundTruthRegra
from aplicacao.avaliacao.permissoes import (
    pode_colaborar_ground_truth,
    pode_congelar_ground_truth,
    pode_validar_ground_truth,
)
from aplicacao.normas.escolhas import SituacaoNorma


def _bloquear(ground_truth):
    if ground_truth.status == StatusGroundTruth.CONGELADO:
        raise ErroAvaliacao("Ground Truth congelado não pode ser alterado.")


def _lock(ground_truth, versao_esperada):
    atual = GroundTruthPrestacao.objects.select_for_update().get(pk=ground_truth.pk)
    if versao_esperada is not None and atual.versao_registro != int(versao_esperada):
        raise ErroConcorrencia("Esta versão foi alterada por outro usuário. Recarregue antes de salvar.")
    _bloquear(atual)
    return atual


def _codigo_familia() -> str:
    numeros = []
    for codigo in GroundTruthPrestacao.objects.values_list("codigo", flat=True).distinct():
        if codigo.startswith("GT-") and codigo[3:].isdigit():
            numeros.append(int(codigo[3:]))
    return f"GT-{(max(numeros) if numeros else 0) + 1:06d}"


def _codigo_achado(ground_truth) -> str:
    numeros = []
    for codigo in GroundTruthAchado.objects.filter(ground_truth=ground_truth).values_list("codigo", flat=True):
        if codigo.startswith("GTA-") and codigo[4:].isdigit():
            numeros.append(int(codigo[4:]))
    return f"GTA-{(max(numeros) if numeros else 0) + 1:06d}"


def _auditar(usuario, acao, ground_truth, extra=None):
    registrar_evento(
        evento=RegistroAuditoria.Evento.GROUND_TRUTH,
        descricao=f"Ground Truth: {acao}.",
        usuario=usuario,
        detalhes={"codigo": ground_truth.codigo, "versao": ground_truth.versao, "acao": acao, **(extra or {})},
    )


def criar_ground_truth(prestacao, usuario, modo, observacoes="", demonstracao=False):
    if not pode_colaborar_ground_truth(usuario):
        raise ErroAvaliacao("Perfil sem permissão para elaborar Ground Truth.")
    ground_truth = GroundTruthPrestacao.objects.create(
        codigo=_codigo_familia(),
        prestacao_contas=prestacao,
        modo=modo,
        observacoes=observacoes,
        responsavel_tecnico=usuario,
        criado_por=usuario,
        dados_demonstracao=demonstracao,
    )
    _auditar(usuario, "criacao", ground_truth)
    return ground_truth


def definir_regra(ground_truth, usuario, regra, resultado_esperado, aplicavel=True, justificativa="", versao_esperada=None):
    if not pode_colaborar_ground_truth(usuario):
        raise ErroAvaliacao("Perfil sem permissão para elaborar Ground Truth.")
    if ground_truth.status != StatusGroundTruth.RASCUNHO:
        raise ErroAvaliacao("Regras só podem ser editadas no rascunho.")
    with transaction.atomic():
        atual = _lock(ground_truth, versao_esperada)
        item, _criado = GroundTruthRegra.objects.update_or_create(
            ground_truth=atual,
            regra=regra,
            defaults={
                "aplicavel": aplicavel,
                "resultado_esperado": resultado_esperado.strip(),
                "justificativa": justificativa,
                "responsavel": usuario,
            },
        )
        atual.versao_registro += 1
        atual.save(update_fields=["versao_registro", "atualizado_em"])
    _auditar(usuario, "alteracao", atual, {"regra": regra.codigo})
    return item


def adicionar_achado(ground_truth, usuario, **dados):
    if not pode_colaborar_ground_truth(usuario):
        raise ErroAvaliacao("Perfil sem permissão para elaborar Ground Truth.")
    if ground_truth.status != StatusGroundTruth.RASCUNHO:
        raise ErroAvaliacao("Achados só podem ser editados no rascunho.")
    normas = list(dados.pop("normas", []))
    for norma in normas:
        if norma.situacao != SituacaoNorma.VIGENTE:
            raise ErroAvaliacao("Norma fora da vigência não fundamenta o Ground Truth.")
    with transaction.atomic():
        atual = _lock(ground_truth, dados.pop("versao_esperada", None))
        achado = GroundTruthAchado.objects.create(
            ground_truth=atual,
            codigo=_codigo_achado(atual),
            criado_por=usuario,
            dados_demonstracao=atual.dados_demonstracao,
            categoria=dados.get("categoria", ""),
            titulo=dados["titulo"],
            descricao=dados.get("descricao", ""),
            fato=dados.get("fato", ""),
            materialidade=dados.get("materialidade"),
            criticidade=dados.get("criticidade") or "baixa",
            prioridade=dados.get("prioridade") or "normal",
            situacao=dados.get("situacao") or "registrado",
            observacao_tecnica=dados.get("observacao_tecnica", ""),
        )
        if dados.get("regras"):
            achado.regras.set(dados["regras"])
        if dados.get("evidencias"):
            achado.evidencias.set(dados["evidencias"])
        if dados.get("documentos"):
            achado.documentos.set(dados["documentos"])
        if normas:
            achado.normas.set(normas)
        if dados.get("trechos"):
            achado.trechos.set(dados["trechos"])
        if dados.get("pessoas"):
            achado.pessoas.set(dados["pessoas"])
        if dados.get("despesas"):
            achado.despesas.set(dados["despesas"])
        if dados.get("pagamentos"):
            achado.pagamentos.set(dados["pagamentos"])
        atual.versao_registro += 1
        atual.save(update_fields=["versao_registro", "atualizado_em"])
    _auditar(usuario, "alteracao", atual, {"achado": achado.codigo})
    return achado


def enviar_validacao(ground_truth, usuario, versao_esperada=None):
    if not pode_colaborar_ground_truth(usuario):
        raise ErroAvaliacao("Perfil sem permissão para enviar o Ground Truth.")
    with transaction.atomic():
        atual = _lock(ground_truth, versao_esperada)
        if atual.status != StatusGroundTruth.RASCUNHO:
            raise ErroAvaliacao("Somente rascunho pode ser enviado para validação.")
        if not atual.regras_referencia.exists() and not atual.achados_referencia.exists():
            raise ErroAvaliacao("O Ground Truth precisa de regra ou achado de referência.")
        atual.status = StatusGroundTruth.EM_VALIDACAO
        atual.versao_registro += 1
        atual.save(update_fields=["status", "versao_registro", "atualizado_em"])
    _auditar(usuario, "envio_validacao", atual)
    return atual


def validar(ground_truth, usuario, versao_esperada=None):
    if not pode_validar_ground_truth(usuario):
        raise ErroAvaliacao("Somente o auditor pode validar o Ground Truth.")
    with transaction.atomic():
        atual = _lock(ground_truth, versao_esperada)
        if atual.status != StatusGroundTruth.EM_VALIDACAO:
            raise ErroAvaliacao("O Ground Truth precisa estar em validação.")
        atual.status = StatusGroundTruth.VALIDADO
        atual.validado_por = usuario
        atual.validado_em = timezone.now()
        atual.versao_registro += 1
        atual.save(update_fields=["status", "validado_por", "validado_em", "versao_registro", "atualizado_em"])
    _auditar(usuario, "validacao", atual)
    return atual


def congelar(ground_truth, usuario, versao_esperada=None):
    if not pode_congelar_ground_truth(usuario):
        raise ErroAvaliacao("Somente o auditor pode congelar o Ground Truth. Permissão administrativa não equivale a autoridade técnica.")
    with transaction.atomic():
        atual = GroundTruthPrestacao.objects.select_for_update().get(pk=ground_truth.pk)
        if versao_esperada is not None and atual.versao_registro != int(versao_esperada):
            raise ErroConcorrencia("Esta versão foi alterada por outro usuário. Recarregue antes de salvar.")
        if atual.status == StatusGroundTruth.CONGELADO:
            raise ErroAvaliacao("Ground Truth congelado não pode ser alterado.")
        if atual.status != StatusGroundTruth.VALIDADO:
            raise ErroAvaliacao("Somente Ground Truth validado pode ser congelado.")
        atual.hash_conteudo = calcular_hash_ground_truth(atual)
        atual.status = StatusGroundTruth.CONGELADO
        atual.congelado_por = usuario
        atual.congelado_em = timezone.now()
        atual.versao_registro += 1
        atual.save()
    _auditar(usuario, "congelamento", atual)
    return atual


def nova_versao(ground_truth, usuario):
    if not pode_colaborar_ground_truth(usuario):
        raise ErroAvaliacao("Perfil sem permissão para versionar o Ground Truth.")
    if ground_truth.status != StatusGroundTruth.CONGELADO:
        raise ErroAvaliacao("A nova versão parte de um Ground Truth congelado.")
    with transaction.atomic():
        novo = GroundTruthPrestacao.objects.create(
            codigo=ground_truth.codigo,
            prestacao_contas=ground_truth.prestacao_contas,
            versao=ground_truth.versao + 1,
            modo=ground_truth.modo,
            observacoes=ground_truth.observacoes,
            responsavel_tecnico=usuario,
            criado_por=usuario,
            dados_demonstracao=ground_truth.dados_demonstracao,
        )
        for regra in ground_truth.regras_referencia.all():
            GroundTruthRegra.objects.create(
                ground_truth=novo,
                regra=regra.regra,
                aplicavel=regra.aplicavel,
                resultado_esperado=regra.resultado_esperado,
                justificativa=regra.justificativa,
                observacao=regra.observacao,
                responsavel=usuario,
            )
        for achado in ground_truth.achados_referencia.all():
            copia = GroundTruthAchado.objects.create(
                codigo=achado.codigo,
                ground_truth=novo,
                categoria=achado.categoria,
                titulo=achado.titulo,
                descricao=achado.descricao,
                fato=achado.fato,
                materialidade=achado.materialidade,
                criticidade=achado.criticidade,
                prioridade=achado.prioridade,
                situacao=achado.situacao,
                observacao_tecnica=achado.observacao_tecnica,
                criado_por=usuario,
                dados_demonstracao=achado.dados_demonstracao,
            )
            copia.regras.set(achado.regras.all())
            copia.evidencias.set(achado.evidencias.all())
            copia.documentos.set(achado.documentos.all())
            copia.normas.set(achado.normas.all())
            copia.trechos.set(achado.trechos.all())
            copia.pessoas.set(achado.pessoas.all())
            copia.despesas.set(achado.despesas.all())
            copia.pagamentos.set(achado.pagamentos.all())
    _auditar(usuario, "nova_versao", novo, {"origem": ground_truth.versao})
    return novo
