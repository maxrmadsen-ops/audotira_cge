"""Verificações reais da fundação. Integrações ainda não implementadas não são simuladas."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from django.conf import settings
from django.db import connection

logger = logging.getLogger("cge.auditoria")


@dataclass
class ComponenteSaude:
    nome: str
    estado: str
    detalhe: str

    def para_exibicao(self) -> dict:
        return asdict(self)


def _componente(nome: str, estado: str, detalhe: str) -> ComponenteSaude:
    return ComponenteSaude(nome=nome, estado=estado, detalhe=detalhe)


def verificar_aplicacao() -> ComponenteSaude:
    from aplicacao.configuracao.versao import ONDA_ATUAL, VERSAO_APLICACAO

    return _componente("Aplicação Django", "Operacional", f"Versão {VERSAO_APLICACAO}, onda {ONDA_ATUAL}.")


def verificar_postgresql() -> ComponenteSaude:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = %s", ["vector"])
            versao = cursor.fetchone()
        if not versao:
            return _componente("PostgreSQL", "Indisponível", "Conexão ativa, extensão pgvector ausente.")
        return _componente("PostgreSQL", "Operacional", f"Conexão ativa. pgvector {versao[0]}.")
    except Exception:
        logger.exception("Falha ao verificar PostgreSQL")
        return _componente("PostgreSQL", "Indisponível", "Não foi possível consultar o banco.")


def verificar_redis() -> ComponenteSaude:
    try:
        import redis

        cliente = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        cliente.ping()
        return _componente("Redis", "Operacional", "Broker respondeu ao ping.")
    except Exception:
        logger.exception("Falha ao verificar Redis")
        return _componente("Redis", "Indisponível", "Não foi possível contactar o Redis.")


def verificar_celery() -> ComponenteSaude:
    try:
        from aplicacao.configuracao.celery import app

        respostas = app.control.ping(timeout=3.0) or []
        if not respostas:
            return _componente("Celery Worker", "Indisponível", "Nenhum worker respondeu.")
        return _componente("Celery Worker", "Operacional", f"{len(respostas)} worker respondeu.")
    except Exception:
        logger.exception("Falha ao verificar Celery")
        return _componente("Celery Worker", "Indisponível", "Não foi possível consultar o worker.")


def verificar_armazenamento() -> ComponenteSaude:
    try:
        raiz = Path(settings.ARQUIVOS_RAIZ)
        raiz.mkdir(parents=True, exist_ok=True)
        alvo = raiz / ".verificacao_saude"
        alvo.write_text("ok", encoding="utf-8")
        alvo.unlink()
        return _componente("Armazenamento", "Operacional", "Volume de arquivos aceita leitura e escrita.")
    except Exception:
        logger.exception("Falha ao verificar armazenamento")
        return _componente("Armazenamento", "Indisponível", "Não foi possível gravar no volume de arquivos.")


def verificar_provedores_nao_configurados() -> list[ComponenteSaude]:
    return [
        _estado_provedor("OpenAI", "openai", settings.OPENAI_HABILITADO, settings.OPENAI_API_KEY),
        _estado_provedor("Anthropic", "anthropic", settings.ANTHROPIC_HABILITADO, settings.ANTHROPIC_API_KEY),
    ]


def _estado_provedor(nome: str, codigo: str, habilitado: bool, chave: str) -> ComponenteSaude:
    if not chave or not habilitado:
        if chave and not habilitado:
            detalhe = "Há chave no ambiente, mas o provedor está desabilitado. Nenhuma chamada foi realizada."
        else:
            detalhe = "Nenhuma chave utilizável. Nenhuma chamada foi realizada."
        return _componente(nome, "Não configurado", detalhe)
    try:
        from aplicacao.inteligencia_artificial.models import EventoOperacionalProvedor

        ultimo = EventoOperacionalProvedor.objects.filter(provedor=codigo).first()
    except Exception:
        logger.exception("Falha ao ler o último erro operacional de IA")
        ultimo = None
    if ultimo is not None:
        return _componente(
            nome,
            "Indisponível",
            f"Último erro operacional: {ultimo.erro_normalizado}. Nenhuma chamada de saúde foi realizada.",
        )
    return _componente(nome, "Configurado", "Provedor habilitado. Nenhuma chamada de saúde foi realizada.")


def verificar_celery_beat() -> ComponenteSaude:
    return _componente(
        "Celery Beat",
        "Não verificado",
        "Esta tela não consulta o agendador e não faz chamada externa.",
    )


def verificar_fila() -> ComponenteSaude:
    try:
        import redis

        cliente = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        aguardando = cliente.llen("celery")
        return _componente("Fila Celery", "Operacional", f"{aguardando} tarefa(s) aguardando na fila celery.")
    except Exception:
        logger.exception("Falha ao ler a fila Celery")
        return _componente("Fila Celery", "Não verificado", "Não foi possível ler a fila local.")


def verificar_migrations() -> ComponenteSaude:
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plano = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        logger.exception("Falha ao verificar migrations")
        return _componente("Migrations", "Não disponível", "Não foi possível ler o plano de migrations.")
    if plano:
        return _componente("Migrations", "Pendente", f"{len(plano)} migration(ões) ainda não aplicada(s).")
    return _componente("Migrations", "Operacional", "Nenhuma migration pendente.")


def coletar_saude() -> list[ComponenteSaude]:
    return [
        verificar_aplicacao(),
        verificar_migrations(),
        verificar_postgresql(),
        verificar_redis(),
        verificar_celery(),
        verificar_celery_beat(),
        verificar_fila(),
        verificar_armazenamento(),
        *verificar_provedores_nao_configurados(),
    ]
