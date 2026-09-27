from django.db import transaction

from aplicacao.achados.escolhas import AcaoRevisao, Criticidade, PapelEvidencia, Prioridade, StatusAchado, TipoEvidencia
from aplicacao.achados.gerador import _novo_codigo
from aplicacao.achados.linguagem import texto_permitido
from aplicacao.achados.models import AchadoEvidencia, Evidencia, RevisaoAchado
from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.usuarios.models import Usuario

ACOES_AUDITOR = {AcaoRevisao.CONFIRMAR, AcaoRevisao.DESCARTAR}
STATUS_POR_ACAO = {
    AcaoRevisao.CONFIRMAR: StatusAchado.CONFIRMADO,
    AcaoRevisao.DESCARTAR: StatusAchado.DESCARTADO,
    AcaoRevisao.AJUSTAR: StatusAchado.AJUSTADO,
    AcaoRevisao.SOLICITAR_DILIGENCIA: StatusAchado.NECESSITA_DILIGENCIA,
    AcaoRevisao.MANTER_EM_ANALISE: StatusAchado.EM_REVISAO,
}


class ErroRevisao(Exception):
    pass


def pode_executar(usuario, acao: str, altera_classificacao: bool = False) -> bool:
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.perfil == Usuario.Perfil.CONSULTA:
        return False
    if acao in ACOES_AUDITOR or altera_classificacao:
        return usuario.perfil in {Usuario.Perfil.AUDITOR, Usuario.Perfil.ADMINISTRADOR}
    return usuario.perfil in {Usuario.Perfil.ANALISTA, Usuario.Perfil.AUDITOR, Usuario.Perfil.ADMINISTRADOR}


def revisar(achado, usuario, acao: str, justificativa: str = "", comentario: str = "", campos: dict | None = None) -> RevisaoAchado:
    campos = campos or {}
    altera_classificacao = any(chave in campos for chave in ("criticidade", "prioridade"))
    if not pode_executar(usuario, acao, altera_classificacao):
        raise ErroRevisao("O perfil não pode registrar esta revisão.")
    if acao == AcaoRevisao.CONFIRMAR and achado.evidencia_insuficiente:
        raise ErroRevisao("Evidência insuficiente — requer avaliação humana.")
    if acao == AcaoRevisao.CONFIRMAR and achado.status == StatusAchado.CONFIRMADO:
        raise ErroRevisao("O achado já está confirmado.")
    status_novo = STATUS_POR_ACAO[acao]
    anterior = _retrato(achado)
    with transaction.atomic():
        if acao == AcaoRevisao.AJUSTAR:
            _aplicar_ajuste(achado, campos)
        elif altera_classificacao:
            _aplicar_classificacao(achado, campos)
        achado.status = status_novo
        achado.save()
        revisao = RevisaoAchado.objects.create(
            achado=achado,
            acao=acao,
            status_anterior=anterior["status"],
            status_novo=status_novo,
            justificativa=texto_permitido(justificativa),
            comentario=texto_permitido(comentario),
            valor_anterior=anterior,
            valor_novo=_retrato(achado),
            usuario=usuario,
        )
    registrar_evento(
        evento=RegistroAuditoria.Evento.REVISAO_HUMANA,
        descricao=f"Revisão {acao} em {achado.codigo}.",
        usuario=usuario,
        caminho=f"/achados/{achado.pk}/",
        detalhes={
            "achado": achado.codigo,
            "acao": acao,
            "status_anterior": anterior["status"],
            "status_novo": status_novo,
        },
    )
    return revisao


def registrar_evidencia_humana(achado, usuario, trecho: str, papel: str = PapelEvidencia.SUPORTA) -> Evidencia:
    if not pode_executar(usuario, AcaoRevisao.AJUSTAR):
        raise ErroRevisao("O perfil não pode associar evidência complementar.")
    evidencia = Evidencia.objects.create(
        codigo=_novo_codigo(Evidencia, "EVD"),
        prestacao_contas=achado.prestacao_contas,
        tipo=TipoEvidencia.HUMANA,
        origem="revisao_humana",
        trecho=texto_permitido(trecho)[:500],
        metodo_obtencao="usuario",
        confiabilidade_origem="media",
        criada_por=usuario,
        demonstracao=achado.demonstracao,
    )
    AchadoEvidencia.objects.get_or_create(achado=achado, evidencia=evidencia, defaults={"papel": papel})
    registrar_evento(
        evento=RegistroAuditoria.Evento.ALTERACAO,
        descricao=f"Evidência humana {evidencia.codigo} associada a {achado.codigo}.",
        usuario=usuario,
        detalhes={"achado": achado.codigo, "evidencia": evidencia.codigo, "tipo": TipoEvidencia.HUMANA},
    )
    return evidencia


def _retrato(achado) -> dict:
    return {
        "status": achado.status,
        "titulo": achado.titulo,
        "descricao_factual": achado.descricao_factual,
        "interpretacao": achado.interpretacao,
        "possivel_implicacao": achado.possivel_implicacao,
        "criticidade": achado.criticidade,
        "prioridade": achado.prioridade,
        "saida_original": achado.saida_original,
    }


def _aplicar_ajuste(achado, campos: dict) -> None:
    for origem, destino in (
        ("titulo", "titulo"),
        ("descricao_factual", "descricao_factual"),
        ("interpretacao", "interpretacao"),
        ("possivel_implicacao", "possivel_implicacao"),
    ):
        if origem in campos:
            setattr(achado, destino, texto_permitido(str(campos[origem]))[: (300 if destino == "titulo" else 4000)])
    _aplicar_classificacao(achado, campos)


def _aplicar_classificacao(achado, campos: dict) -> None:
    if "criticidade" in campos and campos["criticidade"] in Criticidade.values:
        achado.criticidade = campos["criticidade"]
    if "prioridade" in campos and campos["prioridade"] in Prioridade.values:
        achado.prioridade = campos["prioridade"]
