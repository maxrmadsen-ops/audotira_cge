from django.db import transaction
from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.pareceres.escolhas import StatusParecerFinal
from aplicacao.pareceres.models import HistoricoParecerFinal, ParecerFinal
from aplicacao.usuarios.acesso import exigir_atuar_na_prestacao


def _proxima_versao(prestacao) -> int:
    ultima = ParecerFinal.objects.filter(prestacao=prestacao).order_by("-versao").first()
    return (ultima.versao + 1) if ultima else 1


def obter_ou_criar_parecer(*, prestacao, usuario) -> ParecerFinal:
    exigir_atuar_na_prestacao(usuario, prestacao)
    atual = ParecerFinal.objects.filter(prestacao=prestacao).order_by("-versao").first()
    if atual and atual.status != StatusParecerFinal.FINALIZADO:
        return atual
    return ParecerFinal.objects.create(
        prestacao=prestacao,
        versao=_proxima_versao(prestacao),
        autor=usuario,
        demonstracao=prestacao.demonstracao,
    )


def registrar_sugestao_ia(*, parecer: ParecerFinal, usuario, texto: str, request=None) -> ParecerFinal:
    """Guarda sugestão de apoio. Nunca representa decisão administrativa."""
    exigir_atuar_na_prestacao(usuario, parecer.prestacao)
    anterior = parecer.sugestao_ia
    parecer.sugestao_ia = (texto or "").strip()
    parecer.sugestao_gerada_em = timezone.now()
    parecer.save(update_fields=["sugestao_ia", "sugestao_gerada_em", "atualizado_em"])
    HistoricoParecerFinal.objects.create(
        parecer=parecer,
        usuario=usuario,
        acao="sugestao_ia",
        texto_anterior=anterior,
        texto_posterior=parecer.sugestao_ia,
        observacao="Sugestão de texto gerada pelo sistema. Não constitui decisão administrativa.",
    )
    return parecer


def salvar_texto_analista(*, parecer: ParecerFinal, usuario, texto: str, request=None) -> ParecerFinal:
    exigir_atuar_na_prestacao(usuario, parecer.prestacao)
    anterior = parecer.texto_analista
    parecer.texto_analista = (texto or "").strip()
    parecer.autor = usuario
    parecer.elaborada_em = timezone.now()
    parecer.status = StatusParecerFinal.EM_ELABORACAO
    parecer.save(update_fields=["texto_analista", "autor", "elaborada_em", "status", "atualizado_em"])
    HistoricoParecerFinal.objects.create(
        parecer=parecer,
        usuario=usuario,
        acao="texto_analista",
        texto_anterior=anterior,
        texto_posterior=parecer.texto_analista,
    )
    registrar_evento(
        evento=RegistroAuditoria.Evento.ELABORACAO_PARECER,
        descricao=f"Parecer v{parecer.versao} elaborado no processo {parecer.prestacao.numero_processo}",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", "") if request else "",
        detalhes={"parecer_id": parecer.pk, "prestacao_id": parecer.prestacao_id, "versao": parecer.versao},
    )
    return parecer


def aproveitar_sugestao(*, parecer: ParecerFinal, usuario, parcial: bool = False, request=None) -> ParecerFinal:
    """Copia a sugestão da IA para o texto do analista. Não finaliza nem decide."""
    exigir_atuar_na_prestacao(usuario, parecer.prestacao)
    if not parecer.sugestao_ia.strip():
        raise ValueError("Não há sugestão de IA para aproveitar.")
    if parcial and parecer.texto_analista.strip():
        texto = f"{parecer.texto_analista.rstrip()}\n\n{parecer.sugestao_ia.strip()}"
    else:
        texto = parecer.sugestao_ia.strip()
    return salvar_texto_analista(parecer=parecer, usuario=usuario, texto=texto, request=request)


def finalizar_parecer(*, parecer: ParecerFinal, usuario, texto_final: str | None = None, request=None) -> ParecerFinal:
    exigir_atuar_na_prestacao(usuario, parecer.prestacao)
    with transaction.atomic():
        anterior = parecer.texto_final
        if texto_final is not None:
            parecer.texto_final = texto_final.strip()
        elif not parecer.texto_final:
            parecer.texto_final = parecer.texto_analista
        parecer.autor = usuario
        parecer.status = StatusParecerFinal.FINALIZADO
        parecer.finalizada_em = timezone.now()
        parecer.save(update_fields=["texto_final", "autor", "status", "finalizada_em", "atualizado_em"])
        HistoricoParecerFinal.objects.create(
            parecer=parecer,
            usuario=usuario,
            acao="finalizar",
            texto_anterior=anterior,
            texto_posterior=parecer.texto_final,
            observacao="Versão final do analista. A sugestão de IA permanece separada.",
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.ELABORACAO_PARECER,
        descricao=f"Parecer v{parecer.versao} finalizado no processo {parecer.prestacao.numero_processo}",
        usuario=usuario,
        endereco_ip=obter_ip(request),
        caminho=getattr(request, "path", "") if request else "",
        detalhes={"parecer_id": parecer.pk, "status": parecer.status},
    )
    return parecer
