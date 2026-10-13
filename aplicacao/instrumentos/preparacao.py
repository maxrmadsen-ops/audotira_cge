"""Passo 1 da preparação da análise: seleção, processamento e conclusão do instrumento."""

from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.documentos.escolhas import TipoDocumento
from aplicacao.documentos.servico import executar_pipeline
from aplicacao.instrumentos.escolhas import EstadoPreparacao, StatusCampo, StatusCorrespondenciaNorma
from aplicacao.instrumentos.models import PreparacaoInstrumento, TermoCongelado, TermoFomento
from aplicacao.instrumentos.servico import abrir_nova_versao, congelar_termo, estruturar_termo, termo_do_documento


def obter_preparacao(prestacao) -> PreparacaoInstrumento:
    preparacao, _ = PreparacaoInstrumento.objects.get_or_create(prestacao=prestacao)
    return preparacao


def selecionar_documento(preparacao: PreparacaoInstrumento, documento, usuario) -> PreparacaoInstrumento:
    if documento.prestacao_contas_id != preparacao.prestacao_id:
        raise ValueError("O documento não pertence a esta prestação de contas.")
    termo = termo_do_documento(documento)
    if termo and termo.congelado and preparacao.documento_id not in {None, documento.pk}:
        raise TermoCongelado("O instrumento validado desta prestação não é substituído silenciosamente.")
    preparacao.documento = documento
    preparacao.mensagem = ""
    if termo and termo.congelado:
        preparacao.estado = EstadoPreparacao.VALIDADO
    elif documento.paginas.exists():
        preparacao.estado = EstadoPreparacao.EXTRACAO_CONCLUIDA
    else:
        preparacao.estado = EstadoPreparacao.NAO_INICIADO
    preparacao.save()
    registrar_evento(
        evento=RegistroAuditoria.Evento.INSTRUMENTO_SELECIONADO,
        descricao="Instrumento da parceria selecionado",
        usuario=usuario,
        detalhes={"prestacao": preparacao.prestacao_id, "documento": documento.pk},
    )
    return preparacao


def processar_instrumento(preparacao: PreparacaoInstrumento, usuario, reprocessar: bool = False) -> PreparacaoInstrumento:
    documento = preparacao.documento
    if documento is None:
        raise ValueError("Selecione o instrumento antes de processar.")
    termo = termo_do_documento(documento)
    if termo and termo.congelado:
        raise TermoCongelado("Versão validada não é reprocessada. Reabra a validação antes.")
    preparacao.estado = EstadoPreparacao.EM_PROCESSAMENTO
    preparacao.mensagem = ""
    preparacao.save(update_fields=["estado", "mensagem", "atualizado_em"])
    try:
        if not documento.paginas.exists() or reprocessar:
            executar_pipeline(documento.pk, getattr(usuario, "pk", None))
            documento.refresh_from_db()
        with transaction.atomic():
            termo = estruturar_termo(documento)
    except Exception as exc:
        preparacao.estado = EstadoPreparacao.ERRO
        preparacao.mensagem = str(exc)[:255]
        preparacao.save(update_fields=["estado", "mensagem", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.ERRO_PROCESSAMENTO,
            descricao="Falha ao processar o instrumento da parceria",
            usuario=usuario,
            detalhes={"prestacao": preparacao.prestacao_id, "documento": documento.pk, "erro": preparacao.mensagem},
        )
        return preparacao
    atencao = documento.tipo_documento != TipoDocumento.TERMO
    preparacao.estado = EstadoPreparacao.REQUER_ATENCAO if atencao else EstadoPreparacao.AGUARDANDO_VALIDACAO
    preparacao.mensagem = "A classificação não identificou um termo de fomento." if atencao else ""
    preparacao.save(update_fields=["estado", "mensagem", "atualizado_em"])
    evento = RegistroAuditoria.Evento.INSTRUMENTO_REPROCESSADO if reprocessar else RegistroAuditoria.Evento.INSTRUMENTO_PROCESSADO
    registrar_evento(
        evento=evento,
        descricao="Instrumento da parceria processado",
        usuario=usuario,
        detalhes={
            "prestacao": preparacao.prestacao_id,
            "documento": documento.pk,
            "versao": termo.versao,
            "hash_documento": documento.hash_sha256,
            "metodo": termo.metodo_extracao,
        },
    )
    registrar_evento(
        evento=RegistroAuditoria.Evento.INSTRUMENTO_CLASSIFICADO,
        descricao="Classificação do instrumento da parceria",
        usuario=usuario,
        detalhes={
            "prestacao": preparacao.prestacao_id,
            "documento": documento.pk,
            "tipo": documento.tipo_documento,
            "metodo": documento.metodo_classificacao,
        },
    )
    return preparacao


def resumo_validacao(termo: TermoFomento | None) -> dict:
    if termo is None:
        return {
            "identificadas": 0,
            "confirmadas": 0,
            "corrigidas": 0,
            "nao_identificadas": 0,
            "pendentes": 0,
            "referencias": 0,
            "responsavel": "",
            "revisado_em": None,
            "versao": None,
        }
    campos = termo.campos.all()
    ultimo = campos.exclude(validado_em=None).order_by("-validado_em").select_related("validado_por").first()
    responsavel = ""
    revisado_em = None
    if termo.validado_por_id:
        responsavel = str(termo.validado_por)
        revisado_em = termo.validado_em
    elif ultimo and ultimo.validado_por_id:
        responsavel = str(ultimo.validado_por)
        revisado_em = ultimo.validado_em
    return {
        "identificadas": campos.exclude(valor_extraido="").count(),
        "confirmadas": campos.filter(status=StatusCampo.VALIDADO).count(),
        "corrigidas": campos.filter(status=StatusCampo.CORRIGIDO).count(),
        "nao_identificadas": campos.filter(status=StatusCampo.NAO_IDENTIFICADO).count(),
        "pendentes": campos.filter(status__in=[StatusCampo.EXTRAIDO, StatusCampo.AGUARDANDO]).count(),
        "referencias": termo.referencias_normativas.count(),
        "responsavel": responsavel,
        "revisado_em": revisado_em,
        "versao": termo.versao,
    }


def situacao_referencia(referencia) -> str:
    if referencia.norma_id and referencia.status_correspondencia == StatusCorrespondenciaNorma.CORRESPONDENTE:
        return "Já existente no catálogo"
    if referencia.status_correspondencia == StatusCorrespondenciaNorma.SEM_CORRESPONDENCIA:
        return "Pendente de tratamento"
    return "Identificada"


def concluir_validacao(preparacao: PreparacaoInstrumento, usuario, ciente_ausencias: bool = False):
    documento = preparacao.documento
    termo = termo_do_documento(documento) if documento else None
    if termo is None:
        raise ValueError("Processe o instrumento antes de concluir a validação.")
    from aplicacao.instrumentos.unidade_objeto import progresso_da_conferencia

    resumo = progresso_da_conferencia(termo)
    if resumo["pendentes"]:
        raise ValueError("Ainda há unidades documentais sem revisão humana.")
    if resumo["nao_identificadas"] and not ciente_ausencias:
        raise ValueError("Há informações não identificadas. Confirme que a ausência foi revisada.")
    congelar_termo(termo, usuario, com_ressalvas=bool(resumo["nao_identificadas"] or resumo["corrigidas"]))
    preparacao.estado = EstadoPreparacao.VALIDADO
    preparacao.mensagem = ""
    preparacao.save(update_fields=["estado", "mensagem", "atualizado_em"])
    registrar_evento(
        evento=RegistroAuditoria.Evento.VALIDACAO_INSTRUMENTO_CONCLUIDA,
        descricao="Validação do instrumento da parceria concluída",
        usuario=usuario,
        detalhes={
            "prestacao": preparacao.prestacao_id,
            "documento": documento.pk,
            "versao": termo.versao,
            "hash_conteudo": termo.hash_congelado,
            "hash_documento": documento.hash_sha256,
            "estado": preparacao.estado,
            "concluido_em": timezone.now().isoformat(),
        },
    )
    return termo


def reabrir_validacao(preparacao: PreparacaoInstrumento, usuario):
    documento = preparacao.documento
    termo = termo_do_documento(documento) if documento else None
    if termo is None or not termo.congelado:
        raise ValueError("Não há versão validada para reabrir.")
    abrir_nova_versao(termo)
    preparacao.estado = EstadoPreparacao.AGUARDANDO_VALIDACAO
    preparacao.save(update_fields=["estado", "atualizado_em"])
    registrar_evento(
        evento=RegistroAuditoria.Evento.VALIDACAO_INSTRUMENTO_REABERTA,
        descricao="Validação do instrumento reaberta em nova versão",
        usuario=usuario,
        detalhes={"prestacao": preparacao.prestacao_id, "documento": documento.pk, "versao": termo.versao},
    )
    return termo
