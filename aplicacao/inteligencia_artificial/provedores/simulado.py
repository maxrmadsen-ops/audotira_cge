import json

from aplicacao.inteligencia_artificial.provedores.base import (
    ProvedorInteligenciaArtificialBase,
    RequisicaoProvedor,
    RespostaProvedor,
    ErroProvedor,
)


def resposta_padrao(requisicao: RequisicaoProvedor) -> dict:
    return {
        "resultado": "INCONCLUSIVO",
        "justificativa_resumida": "Resposta simulada. Nenhum provedor externo foi chamado.",
        "fatos_identificados": [],
        "fontes_utilizadas": [],
        "fundamentos_normativos": [],
        "limitacoes": ["Provedor simulado. A revisão humana permanece obrigatória."],
        "dados_insuficientes": True,
        "requer_revisao_humana": True,
    }


class ProvedorInteligenciaArtificialSimulado(ProvedorInteligenciaArtificialBase):
    codigo = "simulado"

    def __init__(self, respostas=None, falha: str | None = None, tokens_entrada=12, tokens_saida=8, duracao_ms=5):
        self.respostas = list(respostas or [])
        self.falha = falha
        self.tokens_entrada = tokens_entrada
        self.tokens_saida = tokens_saida
        self.duracao_ms = duracao_ms
        self.chamadas: list[RequisicaoProvedor] = []

    def disponibilidade(self) -> str:
        return "configurado"

    def executar(self, requisicao: RequisicaoProvedor) -> RespostaProvedor:
        self.chamadas.append(requisicao)
        if self.falha:
            raise ErroProvedor(self.falha, "Falha simulada.")
        if self.respostas:
            payload = self.respostas.pop(0)
        else:
            payload = resposta_padrao(requisicao)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = payload
        return RespostaProvedor(
            payload=payload,
            tokens_entrada=self.tokens_entrada,
            tokens_saida=self.tokens_saida,
            id_requisicao="simulado",
            duracao_ms=self.duracao_ms,
        )

    def obter_modelo(self, identificador: str) -> str:
        return identificador or "simulado-estruturado"
