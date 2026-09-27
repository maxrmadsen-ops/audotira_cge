"""Adaptador HTTP da OpenAI. Nenhuma outra camada importa este módulo para falar com o provedor."""

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

URL = "https://api.openai.com/v1/chat/completions"


class ProvedorOpenAI(ProvedorInteligenciaArtificialBase):
    codigo = "openai"

    def disponibilidade(self) -> str:
        if not getattr(settings, "OPENAI_HABILITADO", False):
            return "nao_configurado"
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return "nao_configurado"
        return "configurado"

    def executar(self, requisicao: RequisicaoProvedor) -> RespostaProvedor:
        if self.disponibilidade() != "configurado":
            raise ErroProvedor("nao_configurado")
        corpo = {
            "model": self.obter_modelo(requisicao.modelo),
            "messages": [
                {"role": "system", "content": requisicao.prompt_sistema},
                {"role": "user", "content": requisicao.entrada},
            ],
            "response_format": {"type": "json_object"},
        }
        pedido = urllib.request.Request(
            URL,
            data=json.dumps(corpo).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
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
        conteudo = bruto["choices"][0]["message"]["content"]
        uso = bruto.get("usage") or {}
        return RespostaProvedor(
            payload=extrair_objeto_json(conteudo),
            tokens_entrada=int(uso.get("prompt_tokens") or 0),
            tokens_saida=int(uso.get("completion_tokens") or 0),
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
