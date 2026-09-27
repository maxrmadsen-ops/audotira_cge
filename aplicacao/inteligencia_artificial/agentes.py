from django.conf import settings

from aplicacao.inteligencia_artificial.escolhas import ProvedorIA
from aplicacao.inteligencia_artificial.gerenciador import GerenciadorInteligenciaArtificial
from aplicacao.inteligencia_artificial.models import ConfiguracaoRoteamento, ModeloInteligenciaArtificial
from aplicacao.inteligencia_artificial.preparacao import preparar_contexto
from aplicacao.inteligencia_artificial.provedores.anthropic_adaptador import ProvedorAnthropic
from aplicacao.inteligencia_artificial.provedores.openai_adaptador import ProvedorOpenAI
from aplicacao.inteligencia_artificial.provedores.simulado import ProvedorInteligenciaArtificialSimulado
from aplicacao.inteligencia_artificial.sementes import versao_ativa

MAPA_REGRAS = {
    "PT-002": "compatibilidade_plano",
    **{f"VED-00{indice}": "vedacoes" for indice in range(1, 9)},
    **{f"PRI-00{indice}": "principios" for indice in range(1, 8)},
    **{f"OBJ-00{indice}": "objeto_metas" for indice in range(1, 4)},
}


def construir_provedor(codigo: str):
    if codigo == ProvedorIA.OPENAI:
        return ProvedorOpenAI()
    if codigo == ProvedorIA.ANTHROPIC:
        return ProvedorAnthropic()
    if codigo == ProvedorIA.SIMULADO:
        return ProvedorInteligenciaArtificialSimulado()
    return None


def gerenciador_configurado():
    if getattr(settings, "IA_INTEGRACAO", "desligada") == "desligada":
        return None
    if settings.IA_INTEGRACAO == "simulada":
        modelo = ModeloInteligenciaArtificial.objects.filter(provedor=ProvedorIA.SIMULADO, ativo=True).order_by("-modelo_padrao").first()
        return GerenciadorInteligenciaArtificial(ProvedorInteligenciaArtificialSimulado(), modelo_principal=modelo)
    configuracao = ConfiguracaoRoteamento.objects.filter(ativo=True).select_related("modelo_principal", "modelo_fallback").first()
    if configuracao is None:
        return None
    return GerenciadorInteligenciaArtificial(
        construir_provedor(configuracao.provedor_principal),
        construir_provedor(configuracao.provedor_fallback) if configuracao.provedor_fallback else None,
        configuracao.modelo_principal,
        configuracao.modelo_fallback,
    )


class AgenteBase:
    codigo = "analise_semantica"

    def __init__(self, gerenciador=None):
        self.gerenciador = gerenciador

    def executar(self, regra, contexto_execucao, **kwargs):
        contexto = preparar_contexto(regra, contexto_execucao, kwargs.get("extras"))
        versao = kwargs.get("versao_prompt") or versao_ativa(self.codigo)
        gerenciador = self.gerenciador if self.gerenciador is not None else gerenciador_configurado()
        if gerenciador is None or versao is None:
            return None
        return gerenciador.executar(
            agente=self.codigo,
            contexto=contexto,
            versao_prompt=versao,
            regra=regra,
            prestacao=contexto_execucao.prestacao,
            analise=kwargs.get("analise"),
            laboratorio=kwargs.get("laboratorio", False),
            tentativa=kwargs.get("tentativa", 1),
            chave=kwargs.get("chave"),
        )


class AgenteAnaliseSemantica(AgenteBase):
    codigo = "analise_semantica"


class AgenteCompatibilidadePlanoTrabalho(AgenteBase):
    codigo = "compatibilidade_plano"


class AgenteAnalisePrincipios(AgenteBase):
    codigo = "principios"


class AgenteAnaliseObjetoMetas(AgenteBase):
    codigo = "objeto_metas"


class AgenteAnaliseVedacoes(AgenteBase):
    codigo = "vedacoes"


class AgentePreAnaliseTecnica(AgenteBase):
    """Consolida fatos já produzidos. Não emite o documento de pré-análise."""

    codigo = "pre_analise_tecnica"

    def consolidar(self, execucoes) -> dict:
        fatos = []
        for execucao in execucoes:
            if execucao.regra.codigo.startswith(("SYS-", "ACH-")):
                continue
            fatos.append(
                {
                    "regra": execucao.regra.codigo,
                    "resultado": execucao.resultado_funcional,
                    "origem": f"ExecucaoRegra {execucao.pk}",
                }
            )
        return {
            "resultado": "CONSOLIDAÇÃO INTERNA",
            "parecer": None,
            "documento_final": False,
            "fatos_identificados": fatos,
            "requer_revisao_humana": True,
        }


AGENTES = {
    "analise_semantica": AgenteAnaliseSemantica,
    "compatibilidade_plano": AgenteCompatibilidadePlanoTrabalho,
    "principios": AgenteAnalisePrincipios,
    "objeto_metas": AgenteAnaliseObjetoMetas,
    "vedacoes": AgenteAnaliseVedacoes,
    "pre_analise_tecnica": AgentePreAnaliseTecnica,
}


def classe_do_agente(codigo_regra: str):
    return AGENTES[MAPA_REGRAS.get(codigo_regra, "analise_semantica")]
