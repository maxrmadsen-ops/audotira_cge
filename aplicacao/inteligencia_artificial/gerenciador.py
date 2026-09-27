"""Orquestra provedor, schema, fontes, custo e registro. Não conclui a prestação."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from django.conf import settings
from django.utils import timezone

from aplicacao.inteligencia_artificial.custos import estimar_custo
from aplicacao.inteligencia_artificial.escolhas import ERROS_COM_FALLBACK, ProvedorIA, StatusUso
from aplicacao.inteligencia_artificial.fontes import validar_fontes
from aplicacao.inteligencia_artificial.models import (
    EventoOperacionalProvedor,
    LimiteConsumoInteligenciaArtificial,
    UsoInteligenciaArtificial,
)
from aplicacao.inteligencia_artificial.preparacao import tamanho_contexto
from aplicacao.inteligencia_artificial.provedores.base import ErroProvedor, RequisicaoProvedor
from aplicacao.inteligencia_artificial.schema import RespostaIncompleta, SchemaInvalido, validar_schema

logger = logging.getLogger("cge.ia")


@dataclass
class ResultadoChamada:
    resposta: dict
    usos: list = field(default_factory=list)
    status: str = StatusUso.INCONCLUSIVO
    erro: str = ""
    fallback_utilizado: bool = False
    provedor: str = ""
    modelo: str = ""


def chave_idempotencia(*partes) -> str:
    bruto = "|".join(str(parte) for parte in partes)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


class GerenciadorInteligenciaArtificial:
    def __init__(self, principal, fallback=None, modelo_principal=None, modelo_fallback=None):
        self.principal = principal
        self.fallback = fallback
        self.modelo_principal = modelo_principal
        self.modelo_fallback = modelo_fallback

    def executar(
        self,
        *,
        agente: str,
        contexto: dict,
        versao_prompt,
        regra=None,
        prestacao=None,
        analise=None,
        laboratorio: bool = False,
        tentativa: int = 1,
        chave: str | None = None,
        validador_schema=None,
        tentativas_provedor: int | None = None,
        correcao: str = "",
    ) -> ResultadoChamada:
        chave = chave or chave_idempotencia(
            "laboratorio" if laboratorio else "oficial",
            getattr(analise, "pk", ""),
            getattr(regra, "codigo", ""),
            getattr(versao_prompt, "pk", ""),
            tentativa,
        )
        existente = UsoInteligenciaArtificial.objects.filter(chave_idempotencia=chave, status=StatusUso.SUCESSO).first()
        if existente is not None:
            return ResultadoChamada(
                resposta=existente.resposta_estruturada,
                usos=[existente],
                status=existente.status,
                fallback_utilizado=existente.fallback_utilizado,
                provedor=existente.provedor,
                modelo=existente.identificador_modelo,
            )
        limite = LimiteConsumoInteligenciaArtificial.objects.filter(ativo=True, escopo="chamada").order_by("id").first()
        maximo = limite.max_caracteres_contexto if limite else int(getattr(settings, "IA_MAX_CARACTERES_CONTEXTO", 12000))
        if tentativas_provedor is not None:
            tentativas = max(1, int(tentativas_provedor))
        else:
            tentativas = limite.max_tentativas if limite else int(getattr(settings, "IA_MAX_TENTATIVAS", 2))
        if tamanho_contexto(contexto) > maximo:
            uso = self._registrar(
                provedor=self.principal.codigo,
                modelo=self.modelo_principal,
                identificador=getattr(self.modelo_principal, "identificador_modelo", "") or "",
                agente=agente,
                regra=regra,
                prestacao=prestacao,
                analise=analise,
                versao_prompt=versao_prompt,
                laboratorio=laboratorio,
                tentativa=tentativa,
                chave=chave,
                status=StatusUso.LIMITE_EXCEDIDO,
                erro="contexto_excedido",
                resposta=_inconclusivo("Contexto acima do limite configurado. Nenhuma chamada externa foi feita."),
                tokens_entrada=0,
                tokens_saida=0,
                duracao_ms=0,
                id_requisicao="",
                fallback=False,
                provedor_original=self.principal.codigo,
            )
            return ResultadoChamada(resposta=uso.resposta_estruturada, usos=[uso], status=uso.status, erro="contexto_excedido", provedor=uso.provedor)
        payload, meta, erro = self._tentar(
            self.principal,
            self.modelo_principal,
            contexto,
            versao_prompt,
            tentativas,
            validador_schema or validar_schema,
            correcao,
        )
        usos = []
        if meta is not None:
            usos.append(
                self._registrar(
                    provedor=self.principal.codigo,
                    modelo=self.modelo_principal,
                    identificador=self._identificador(self.modelo_principal, self.principal),
                    agente=agente,
                    regra=regra,
                    prestacao=prestacao,
                    analise=analise,
                    versao_prompt=versao_prompt,
                    laboratorio=laboratorio,
                    tentativa=tentativa,
                    chave=chave if erro not in ERROS_COM_FALLBACK or self.fallback is None else chave_idempotencia(chave, "principal"),
                    status=StatusUso.SUCESSO if erro == "" else StatusUso.ERRO_CONTROLADO,
                    erro=erro,
                    resposta=payload or _inconclusivo(erro or "Falha controlada."),
                    tokens_entrada=meta["tokens_entrada"],
                    tokens_saida=meta["tokens_saida"],
                    duracao_ms=meta["duracao_ms"],
                    id_requisicao=meta["id_requisicao"],
                    fallback=False,
                    provedor_original=self.principal.codigo,
                )
            )
        else:
            usos.append(
                self._registrar(
                    provedor=self.principal.codigo,
                    modelo=self.modelo_principal,
                    identificador=self._identificador(self.modelo_principal, self.principal),
                    agente=agente,
                    regra=regra,
                    prestacao=prestacao,
                    analise=analise,
                    versao_prompt=versao_prompt,
                    laboratorio=laboratorio,
                    tentativa=tentativa,
                    chave=chave_idempotencia(chave, "principal") if self.fallback else chave,
                    status=StatusUso.ERRO_CONTROLADO,
                    erro=erro or "erro_tecnico",
                    resposta=_inconclusivo(erro or "Falha controlada."),
                    tokens_entrada=0,
                    tokens_saida=0,
                    duracao_ms=0,
                    id_requisicao="",
                    fallback=False,
                    provedor_original=self.principal.codigo,
                )
            )
        if erro and erro in ERROS_COM_FALLBACK and self.fallback is not None:
            EventoOperacionalProvedor.objects.create(provedor=self.principal.codigo, erro_normalizado=erro)
            payload_fb, meta_fb, erro_fb = self._tentar(
                self.fallback,
                self.modelo_fallback,
                contexto,
                versao_prompt,
                tentativas,
                validador_schema or validar_schema,
                "",
            )
            usos.append(
                self._registrar(
                    provedor=self.fallback.codigo,
                    modelo=self.modelo_fallback,
                    identificador=self._identificador(self.modelo_fallback, self.fallback),
                    agente=agente,
                    regra=regra,
                    prestacao=prestacao,
                    analise=analise,
                    versao_prompt=versao_prompt,
                    laboratorio=laboratorio,
                    tentativa=tentativa,
                    chave=chave_idempotencia(chave, "fallback"),
                    status=StatusUso.SUCESSO if erro_fb == "" else StatusUso.ERRO_CONTROLADO,
                    erro=erro_fb,
                    resposta=payload_fb or _inconclusivo(erro_fb or "Fallback sem resposta válida."),
                    tokens_entrada=(meta_fb or {}).get("tokens_entrada", 0),
                    tokens_saida=(meta_fb or {}).get("tokens_saida", 0),
                    duracao_ms=(meta_fb or {}).get("duracao_ms", 0),
                    id_requisicao=(meta_fb or {}).get("id_requisicao", ""),
                    fallback=True,
                    provedor_original=self.principal.codigo,
                )
            )
            if erro_fb:
                EventoOperacionalProvedor.objects.create(provedor=self.fallback.codigo, erro_normalizado=erro_fb)
            return ResultadoChamada(
                resposta=usos[-1].resposta_estruturada,
                usos=usos,
                status=usos[-1].status,
                erro=erro_fb,
                fallback_utilizado=True,
                provedor=self.fallback.codigo,
                modelo=usos[-1].identificador_modelo,
            )
        if erro:
            EventoOperacionalProvedor.objects.create(provedor=self.principal.codigo, erro_normalizado=erro)
        return ResultadoChamada(
            resposta=usos[-1].resposta_estruturada,
            usos=usos,
            status=usos[-1].status,
            erro=erro,
            fallback_utilizado=False,
            provedor=self.principal.codigo,
            modelo=usos[-1].identificador_modelo,
        )

    def _tentar(self, provedor, modelo, contexto, versao_prompt, tentativas: int, validador_schema, correcao: str = ""):
        identificador = self._identificador(modelo, provedor)
        ultimo = "erro_tecnico"
        diagnostico = ["schema_invalido"]
        meta = None
        entrada = versao_prompt.template_entrada.replace("{{contexto}}", json.dumps(contexto, ensure_ascii=False))
        if correcao:
            entrada = f"{entrada}\n\nCORRECAO_ESTRUTURAL:\n{correcao}"
        for numero in range(1, tentativas + 1):
            requisicao = RequisicaoProvedor(
                modelo=identificador,
                prompt_sistema=versao_prompt.prompt_sistema,
                entrada=entrada,
                schema=versao_prompt.schema_saida or {},
            )
            resposta = None
            try:
                resposta = provedor.executar(requisicao)
                payload = validador_schema(provedor.normalizar(resposta))
                payload = self._aplicar_fontes(contexto, payload)
                return payload, _telemetria(resposta), ""
            except RespostaIncompleta as erro:
                return _falha_estrutural("resposta_incompleta", erro.diagnostico), _telemetria(resposta), "resposta_incompleta"
            except SchemaInvalido as erro:
                ultimo = "schema_invalido"
                diagnostico = [_codigo_diagnostico(erro.motivo)]
                meta = _telemetria(resposta)
                continue
            except ErroProvedor as erro:
                if erro.codigo == "schema_invalido":
                    ultimo = "schema_invalido"
                    diagnostico = ["json_invalido"]
                    meta = _telemetria(resposta, erro.telemetria)
                    continue
                return None, _telemetria(resposta, erro.telemetria), erro.codigo
            except Exception:
                logger.info("uso agente falhou provedor=%s tentativa=%s", provedor.codigo, numero)
                return None, None, "erro_tecnico"
        return _falha_estrutural(ultimo, diagnostico), meta, ultimo

    def _aplicar_fontes(self, contexto: dict, payload: dict) -> dict:
        ok, rejeitadas, fundamentos_ok, fundamentos_rejeitados = validar_fontes(contexto, payload)
        if rejeitadas or fundamentos_rejeitados:
            payload["fontes_utilizadas"] = ok
            payload["fundamentos_normativos"] = fundamentos_ok
            payload["fontes_rejeitadas"] = rejeitadas + fundamentos_rejeitados
            payload["resultado"] = "INCONCLUSIVO"
            payload["dados_insuficientes"] = True
            payload["limitacoes"] = list(payload["limitacoes"]) + ["Fonte não fornecida no contexto foi rejeitada e não é evidência."]
        payload["requer_revisao_humana"] = True
        return payload

    def _identificador(self, modelo, provedor) -> str:
        if modelo is not None and modelo.identificador_modelo:
            return modelo.identificador_modelo
        return provedor.obter_modelo("")

    def _registrar(self, **dados) -> UsoInteligenciaArtificial:
        agora = timezone.now()
        entrada, saida, total = estimar_custo(
            dados["modelo"],
            dados["tokens_entrada"],
            dados["tokens_saida"],
            agora,
        )
        uso = UsoInteligenciaArtificial.objects.create(
            provedor=dados["provedor"] if dados["provedor"] in ProvedorIA.values else ProvedorIA.SIMULADO,
            modelo=dados["modelo"],
            identificador_modelo=dados["identificador"],
            agente=dados["agente"],
            regra=dados["regra"],
            execucao_analise=dados["analise"],
            prestacao_contas=dados["prestacao"],
            iniciada_em=agora,
            finalizada_em=agora,
            duracao_ms=dados["duracao_ms"],
            tokens_entrada=dados["tokens_entrada"],
            tokens_saida=dados["tokens_saida"],
            tokens_total=dados["tokens_entrada"] + dados["tokens_saida"],
            custo_estimado_entrada=entrada,
            custo_estimado_saida=saida,
            custo_estimado_total=total,
            status=dados["status"],
            erro_normalizado=dados["erro"],
            id_requisicao_provedor=dados["id_requisicao"],
            versao_prompt=dados["versao_prompt"],
            fallback_utilizado=dados["fallback"],
            tentativa=dados["tentativa"],
            chave_idempotencia=dados["chave"],
            laboratorio=dados["laboratorio"],
            resposta_estruturada=dados["resposta"],
            provedor_original=dados["provedor_original"],
        )
        versao = dados["versao_prompt"]
        if versao is not None and not versao.utilizada:
            versao.utilizada = True
            versao.save(update_fields=["utilizada"])
        logger.info(
            "uso=%s provedor=%s modelo=%s status=%s tokens=%s duracao_ms=%s fallback=%s",
            uso.pk,
            uso.provedor,
            uso.identificador_modelo,
            uso.status,
            uso.tokens_total,
            uso.duracao_ms,
            uso.fallback_utilizado,
        )
        return uso


def _telemetria(resposta, extra: dict | None = None):
    origem = extra or {}
    if resposta is None and not origem:
        return None
    if resposta is not None:
        return {
            "tokens_entrada": int(resposta.tokens_entrada or 0),
            "tokens_saida": int(resposta.tokens_saida or 0),
            "duracao_ms": int(resposta.duracao_ms or 0),
            "id_requisicao": resposta.id_requisicao or "",
        }
    return {
        "tokens_entrada": int(origem.get("tokens_entrada") or 0),
        "tokens_saida": int(origem.get("tokens_saida") or 0),
        "duracao_ms": int(origem.get("duracao_ms") or 0),
        "id_requisicao": str(origem.get("id_requisicao") or "")[:120],
    }


def _falha_estrutural(codigo: str, diagnostico: list[str]) -> dict:
    payload = _inconclusivo(codigo)
    payload["diagnostico_estrutural"] = [item for item in diagnostico if item][:12] or [codigo]
    return payload


def _codigo_diagnostico(motivo: str) -> str:
    bruto = (motivo or "schema_invalido").strip().split(":", 1)[0]
    if bruto.replace("_", "").isalnum() and len(bruto) <= 40:
        return bruto
    return "schema_invalido"


def _inconclusivo(motivo: str) -> dict:
    return {
        "resultado": "INCONCLUSIVO",
        "justificativa_resumida": motivo[:1000],
        "fatos_identificados": [],
        "fontes_utilizadas": [],
        "fundamentos_normativos": [],
        "limitacoes": [motivo[:500]],
        "dados_insuficientes": True,
        "requer_revisao_humana": True,
    }
