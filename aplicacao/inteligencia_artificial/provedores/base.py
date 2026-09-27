import json
import re
import urllib.error
from dataclasses import dataclass, field

_SEGREDO = re.compile(r"(sk-[A-Za-z0-9_\-]{6,}|Bearer\s+\S+)", re.IGNORECASE)


class ErroProvedor(Exception):
    def __init__(self, codigo: str, mensagem: str = ""):
        self.codigo = codigo
        super().__init__(mensagem or codigo)


@dataclass
class RequisicaoProvedor:
    modelo: str
    prompt_sistema: str
    entrada: str
    schema: dict = field(default_factory=dict)


@dataclass
class RespostaProvedor:
    payload: dict
    tokens_entrada: int
    tokens_saida: int
    id_requisicao: str
    duracao_ms: int
    texto_bruto_ignorado: bool = True


class ProvedorInteligenciaArtificialBase:
    codigo = ""

    def executar(self, requisicao: RequisicaoProvedor) -> RespostaProvedor:
        raise NotImplementedError

    def disponibilidade(self) -> str:
        raise NotImplementedError

    def obter_modelo(self, identificador: str) -> str:
        return identificador

    def metricas(self, resposta: RespostaProvedor) -> dict:
        return {
            "tokens_entrada": resposta.tokens_entrada,
            "tokens_saida": resposta.tokens_saida,
            "tokens_total": resposta.tokens_entrada + resposta.tokens_saida,
            "duracao_ms": resposta.duracao_ms,
        }

    def tratar_erro(self, erro: Exception) -> ErroProvedor:
        if isinstance(erro, ErroProvedor):
            return erro
        if isinstance(erro, urllib.error.HTTPError):
            return classificar_erro_http(erro)
        return ErroProvedor("erro_tecnico", "Falha técnica do provedor.")

    def normalizar(self, resposta: RespostaProvedor) -> dict:
        if not isinstance(resposta.payload, dict):
            raise ErroProvedor("schema_invalido", "Resposta sem objeto.")
        return resposta.payload


def detalhe_http_sanitizado(erro: urllib.error.HTTPError) -> str:
    try:
        bruto = erro.read(600).decode("utf-8", errors="replace")
    except Exception:
        return ""
    bruto = _SEGREDO.sub("[redigido]", bruto)
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        return ""
    erro_obj = dados.get("error") if isinstance(dados, dict) else None
    if not isinstance(erro_obj, dict):
        if isinstance(dados, dict) and dados.get("type"):
            return str(dados.get("type"))[:80]
        return ""
    tipo = str(erro_obj.get("type") or "")[:60]
    codigo = str(erro_obj.get("code") or "")[:60]
    mensagem = " ".join(_SEGREDO.sub("[redigido]", str(erro_obj.get("message") or "")).split())[:160]
    return " | ".join(parte for parte in (tipo, codigo, mensagem) if parte)[:240]


def classificar_erro_http(erro: urllib.error.HTTPError) -> ErroProvedor:
    detalhe = detalhe_http_sanitizado(erro)
    texto = detalhe.lower()
    if erro.code == 401 or "authentication" in texto or "invalid_api_key" in texto:
        return ErroProvedor("authentication_error", detalhe or "authentication_error")
    if erro.code == 403 or "permission" in texto:
        return ErroProvedor("permission_error", detalhe or "permission_error")
    if erro.code == 404 or "model_not_found" in texto or "not_found_error" in texto:
        return ErroProvedor("model_not_found", detalhe or "model_not_found")
    if erro.code == 429:
        return ErroProvedor("rate_limit", detalhe or "rate_limit")
    if erro.code == 408:
        return ErroProvedor("timeout", detalhe or "timeout")
    if erro.code in {502, 503, 504}:
        return ErroProvedor("indisponibilidade", detalhe or "indisponibilidade")
    if erro.code >= 500:
        return ErroProvedor("erro_transitorio", detalhe or "erro_transitorio")
    return ErroProvedor("erro_tecnico", detalhe or "erro_tecnico")


def extrair_objeto_json(texto: str) -> dict:
    limpo = (texto or "").strip()
    if limpo.startswith("```"):
        linhas = limpo.splitlines()
        if linhas and linhas[0].startswith("```"):
            linhas = linhas[1:]
        if linhas and linhas[-1].strip() == "```":
            linhas = linhas[:-1]
        limpo = "\n".join(linhas).strip()
    try:
        payload = json.loads(limpo)
    except json.JSONDecodeError:
        raise ErroProvedor("schema_invalido", "A resposta não é JSON.") from None
    if not isinstance(payload, dict):
        raise ErroProvedor("schema_invalido", "A resposta não é um objeto.")
    return payload
