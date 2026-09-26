from django.utils import timezone

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import registrar_evento
from aplicacao.documentos.armazenamento import ErroArmazenamento
from aplicacao.documentos.extracao import ErroExtracao, ExtratorPDF
from aplicacao.normas.armazenamento import ler_arquivo
from aplicacao.normas.chunking import gerar_chunks
from aplicacao.normas.embeddings import GerenciadorEmbeddings
from aplicacao.normas.escolhas import StatusProcessamentoNorma
from aplicacao.normas.models import Norma, ReprocessamentoNorma, TrechoNormativo
from aplicacao.normas.segmentacao import segmentar


def executar_pipeline(norma_id: int, usuario_id: int | None = None, reprocessamento_id: int | None = None) -> None:
    norma = Norma.objects.filter(pk=norma_id).first()
    if norma is None:
        return
    usuario = _usuario(usuario_id)
    try:
        _marcar(norma, StatusProcessamentoNorma.VALIDANDO)
        if not norma.arquivo:
            raise ErroExtracao("A norma não possui arquivo de fonte.")
        caminho = ler_arquivo(norma.arquivo)
        _marcar(norma, StatusProcessamentoNorma.EXTRAINDO)
        paginas = ExtratorPDF().extrair(caminho)
        _marcar(norma, StatusProcessamentoNorma.SEGMENTANDO)
        blocos = segmentar(paginas)
        chunks = gerar_chunks(blocos)
        _marcar(norma, StatusProcessamentoNorma.INDEXANDO)
        embeddings = GerenciadorEmbeddings()
        vetores = embeddings.incorporar([chunk["texto"] for chunk in chunks])
        TrechoNormativo.objects.filter(norma=norma).delete()
        for chunk, vetor in zip(chunks, vetores, strict=True):
            TrechoNormativo.objects.create(
                norma=norma,
                embedding=vetor,
                provedor_embedding=embeddings.provedor.nome,
                modelo_embedding=embeddings.provedor.modelo,
                dimensao_embedding=embeddings.provedor.dimensao,
                **chunk,
            )
        norma.status_processamento = StatusProcessamentoNorma.DISPONIVEL
        norma.erro_processamento = ""
        norma.save(update_fields=["status_processamento", "erro_processamento", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.PROCESSAMENTO,
            descricao="Norma indexada para consulta.",
            usuario=usuario,
            detalhes={"norma_id": norma.id, "hash_sha256": norma.hash_sha256, "trechos": len(chunks)},
        )
        if reprocessamento_id:
            ReprocessamentoNorma.objects.filter(pk=reprocessamento_id).update(resultado="concluido")
    except (ErroExtracao, ErroArmazenamento, Exception) as exc:
        mensagem = getattr(exc, "mensagem", None) or "Falha ao processar a norma."
        if not isinstance(exc, (ErroExtracao, ErroArmazenamento)):
            mensagem = "Falha ao processar a norma."
        norma.status_processamento = StatusProcessamentoNorma.ERRO
        norma.erro_processamento = str(mensagem)[:500]
        norma.save(update_fields=["status_processamento", "erro_processamento", "atualizado_em"])
        registrar_evento(
            evento=RegistroAuditoria.Evento.ERRO_PROCESSAMENTO,
            descricao=norma.erro_processamento,
            usuario=usuario,
            detalhes={"norma_id": norma.id, "hash_sha256": norma.hash_sha256},
        )
        if reprocessamento_id:
            ReprocessamentoNorma.objects.filter(pk=reprocessamento_id).update(resultado="erro")


def criar_nova_versao(norma: Norma, *, usuario=None, conteudo: bytes | None = None, nome_original: str = "", dados: dict | None = None) -> Norma:
    """Preserva a versão anterior. Conteúdo ou vigência novos não apagam o histórico."""
    from aplicacao.documentos.validacao import validar_envio
    from aplicacao.normas.armazenamento import armazenar_pdf

    dados = dados or {}
    info = None
    if conteudo:
        info = validar_envio(nome_original or norma.nome_original or "norma.pdf", conteudo)
    nova = Norma.objects.create(
        grupo_id=norma.grupo_id,
        versao=norma.versao + 1,
        norma_anterior=norma,
        tipo_norma=dados.get("tipo_norma", norma.tipo_norma),
        numero=dados.get("numero", norma.numero),
        ano=dados.get("ano", norma.ano),
        titulo=dados.get("titulo", norma.titulo),
        ementa=dados.get("ementa", norma.ementa),
        orgao_emissor=dados.get("orgao_emissor", norma.orgao_emissor),
        esfera=dados.get("esfera", norma.esfera),
        data_publicacao=dados.get("data_publicacao", norma.data_publicacao),
        inicio_vigencia=dados.get("inicio_vigencia", norma.inicio_vigencia),
        fim_vigencia=dados.get("fim_vigencia", norma.fim_vigencia),
        situacao=dados.get("situacao", norma.situacao),
        fonte=dados.get("fonte", norma.fonte),
        observacoes=dados.get("observacoes", norma.observacoes),
        nome_original=nome_original or norma.nome_original,
        hash_sha256=norma.hash_sha256,
        status_processamento=StatusProcessamentoNorma.RECEBIDA if conteudo else StatusProcessamentoNorma.DISPONIVEL,
        criado_por=usuario if getattr(usuario, "is_authenticated", False) else norma.criado_por,
    )
    if info:
        nova.arquivo = armazenar_pdf(nova.pk, conteudo)
        nova.hash_sha256 = info["hash_sha256"]
        nova.nome_original = nome_original or nova.nome_original
        nova.save(update_fields=["arquivo", "hash_sha256", "nome_original", "atualizado_em"])
    else:
        nova.arquivo = norma.arquivo
        nova.hash_sha256 = norma.hash_sha256
        nova.save(update_fields=["arquivo", "hash_sha256", "atualizado_em"])
        for trecho in list(norma.trechos.all()):
            trecho.pk = None
            trecho.norma = nova
            trecho.save()
    norma.desativada_em = timezone.now()
    norma.save(update_fields=["desativada_em", "atualizado_em"])
    registrar_evento(
        evento=RegistroAuditoria.Evento.ALTERACAO,
        descricao="Nova versão lógica da norma.",
        usuario=usuario,
        detalhes={"norma_anterior_id": norma.id, "norma_id": nova.id, "versao": nova.versao, "hash_sha256": nova.hash_sha256},
    )
    return nova


def _marcar(norma: Norma, status: str) -> None:
    norma.status_processamento = status
    norma.save(update_fields=["status_processamento", "atualizado_em"])


def _usuario(usuario_id: int | None):
    if not usuario_id:
        return None
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=usuario_id).first()
