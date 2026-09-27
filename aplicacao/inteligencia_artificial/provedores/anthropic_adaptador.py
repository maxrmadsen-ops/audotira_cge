"""Adaptador HTTP da Anthropic. O restante da aplicação não conhece este contrato."""

import json
import socket
import time
import urllib.error
import urllib.request

from django.conf import settings

from aplicacao.inteligencia_artificial.provedores.base import (
    ErroProvedor,
    ProvedorInteligenciaArtificialBase,
    RequisicaoProvedor,
    RespostaProvedor,
    classificar_erro_http,
    extrair_objeto_json,
)

URL = "https://api.anthropic.com/v1/messages"


class ProvedorAnthropic(ProvedorInteligenciaArtificialBase):
    codigo = "anthropic"

    def disponibilidade(self) -> str:
        if not getattr(settings, "ANTHROPIC_HABILITADO", False):
            return "nao_configurado"
        if not getattr(settings, "ANTHROPIC_API_KEY", ""):
            return "nao_configurado"
        return "configurado"

    def executar(self, requisicao: RequisicaoProvedor) -> RespostaProvedor:
        if self.disponibilidade() != "configurado":
            raise ErroProvedor("nao_configurado")
        corpo = {
            "model": self.obter_modelo(requisicao.modelo),
            "max_tokens": 800,
            "system": requisicao.prompt_sistema,
            "messages": [{"role": "user", "content": requisicao.entrada}],
        }
        pedido = urllib.request.Request(
            URL,
            data=json.dumps(corpo).encode("utf-8"),
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        inicio = time.perf_counter()
        try:
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                bruto = json.loads(resposta.read().decode("utf-8"))
        except Exception as erro:
            raise self.tratar_erro(erro) from None
        duracao = int((time.perf_counter() - inicio) * 1000)
        blocos = [bloco.get("text", "") for bloco in bruto.get("content") or [] if bloco.get("type") == "text"]
        uso = bruto.get("usage") or {}
        return RespostaProvedor(
            payload=extrair_objeto_json("".join(blocos)),
            tokens_entrada=int(uso.get("input_tokens") or 0),
            tokens_saida=int(uso.get("output_tokens") or 0),
            id_requisicao=str(bruto.get("id") or "")[:120],
            duracao_ms=duracao,
        )

    def tratar_erro(self, erro: Exception) -> ErroProvedor:
        if isinstance(erro, ErroProvedor):
            return erro
        if isinstance(erro, (TimeoutError, socket.timeout)):
            return ErroProvedor("timeout")
        if isinstance(erro, urllib.error.HTTPError):
            return classificar_erro_http(erro)
        if isinstance(erro, urllib.error.URLError):
            return ErroProvedor("indisponibilidade")
        return ErroProvedor("erro_tecnico")
