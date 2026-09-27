import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from aplicacao.inteligencia_artificial.custos import estimar_custo
from aplicacao.inteligencia_artificial.escolhas import StatusUso
from aplicacao.inteligencia_artificial.fontes import validar_fontes
from aplicacao.inteligencia_artificial.gerenciador import chave_idempotencia
from aplicacao.inteligencia_artificial.models import UsoInteligenciaArtificial
from aplicacao.inteligencia_artificial.provedores.anthropic_adaptador import ProvedorAnthropic
from aplicacao.inteligencia_artificial.provedores.base import ErroProvedor, RequisicaoProvedor
from aplicacao.inteligencia_artificial.provedores.openai_adaptador import ProvedorOpenAI
from aplicacao.inteligencia_artificial.schema import SchemaInvalido, validar_schema
from aplicacao.inteligencia_artificial.sementes import PROMPT_SISTEMA, SCHEMA
from aplicacao.regras.models import ExecucaoRegra

ENTRADA = (
    "DOCUMENTO SINTÉTICO (tipo=documento, identificador=documento-sintetico):\n"
    "O relatório anual de execução foi apresentado em 10/01/2025. "
    "O instrumento exigia a apresentação do relatório até 31/01/2025.\n\n"
    "PERGUNTA:\n"
    "Existe evidência suficiente para afirmar que o relatório foi apresentado dentro do prazo?\n\n"
    "Responda somente um objeto JSON com as chaves resultado, justificativa_resumida, "
    "fatos_identificados, fontes_utilizadas, fundamentos_normativos, limitacoes, "
    "dados_insuficientes e requer_revisao_humana. "
    "resultado não pode ser REGULAR, IRREGULAR, APROVADO ou REPROVADO. "
    "Se citar o documento, use somente {\"tipo\":\"documento\",\"identificador\":\"documento-sintetico\"}. "
    "requer_revisao_humana deve ser true. dados_insuficientes deve ser booleano. "
    "As listas podem ser vazias. Não inclua raciocínio fora do JSON."
)

CONTEXTO = {"itens": [{"tipo": "documento", "identificador": "documento-sintetico"}]}


class Command(BaseCommand):
    help = "Chamada mínima e opcional aos provedores reais. A suíte de testes não executa este comando."

    def handle(self, *args, **options):
        if settings.IA_INTEGRACAO != "configurada":
            raise CommandError("Defina IA_INTEGRACAO=configurada no .env para autorizar chamada real. Nada foi enviado.")
        execucoes_antes = ExecucaoRegra.objects.count()
        falhas = []
        for nome, provedor, habilitado, variavel in (
            ("OpenAI", ProvedorOpenAI(), settings.OPENAI_HABILITADO, "OPENAI_MODELO_PADRAO"),
            ("Anthropic", ProvedorAnthropic(), settings.ANTHROPIC_HABILITADO, "ANTHROPIC_MODELO_PADRAO"),
        ):
            if not habilitado or provedor.disponibilidade() != "configurado":
                self.stdout.write(f"{nome}: não configurado")
                falhas.append(nome)
                continue
            modelo = os.environ.get(variavel, "").strip()
            if not modelo or modelo.lower().startswith("sk-") or len(modelo) > 80:
                self.stdout.write(f"{nome}: modelo ausente na variável {variavel}. Nada foi enviado.")
                falhas.append(nome)
                continue
            falhou = self._chamar(nome, provedor, modelo)
            if falhou:
                falhas.append(nome)
        if ExecucaoRegra.objects.count() != execucoes_antes:
            raise CommandError("A chamada alterou ExecucaoRegra.")
        if falhas:
            raise CommandError("Provedor sem sucesso: " + ", ".join(falhas))

    def _chamar(self, nome, provedor, modelo) -> bool:
        iniciada = timezone.now()
        inicio = time.perf_counter()
        resposta = None
        erro = None
        try:
            resposta = provedor.executar(
                RequisicaoProvedor(
                    modelo=provedor.obter_modelo(modelo),
                    prompt_sistema=PROMPT_SISTEMA,
                    entrada=ENTRADA,
                    schema=SCHEMA,
                )
            )
        except ErroProvedor as capturado:
            erro = capturado
        duracao = int((time.perf_counter() - inicio) * 1000)
        if resposta is not None and resposta.duracao_ms:
            duracao = resposta.duracao_ms
        payload = {}
        status = StatusUso.ERRO_CONTROLADO
        codigo = ""
        schema_valido = False
        if erro is not None:
            codigo = erro.codigo
            mensagem = " ".join(str(erro).split())[:240]
        else:
            try:
                payload = validar_schema(resposta.payload)
                payload = self._aplicar_fontes(payload)
                schema_valido = True
                codigo = ""
                mensagem = ""
                status = StatusUso.INCONCLUSIVO if payload.get("resultado") == "INCONCLUSIVO" else StatusUso.SUCESSO
            except SchemaInvalido as invalido:
                codigo = "schema_invalido"
                mensagem = " ".join(invalido.motivo.split())[:240]
                payload = {}
        uso = self._registrar(
            provedor=provedor.codigo,
            modelo=modelo,
            iniciada=iniciada,
            duracao=duracao,
            tokens_entrada=0 if resposta is None else resposta.tokens_entrada,
            tokens_saida=0 if resposta is None else resposta.tokens_saida,
            status=status,
            erro=codigo,
            id_requisicao="" if resposta is None else resposta.id_requisicao,
            payload=payload,
        )
        custo = "nulo" if uso.custo_estimado_total is None else str(uso.custo_estimado_total)
        self.stdout.write(
            f"{nome} modelo={modelo} status={uso.status} latencia_ms={uso.duracao_ms} "
            f"tokens_entrada={uso.tokens_entrada} tokens_saida={uso.tokens_saida} "
            f"tokens_total={uso.tokens_total} custo={custo} "
            f"resultado={payload.get('resultado', '')} schema_valido={'sim' if schema_valido else 'nao'} "
            f"uso_id={uso.pk} erro={codigo} detalhe={mensagem}"
        )
        return erro is not None or not schema_valido

    def _aplicar_fontes(self, payload: dict) -> dict:
        ok, rejeitadas, fundamentos_ok, fundamentos_rejeitados = validar_fontes(CONTEXTO, payload)
        if rejeitadas or fundamentos_rejeitados:
            payload["fontes_utilizadas"] = ok
            payload["fundamentos_normativos"] = fundamentos_ok
            payload["fontes_rejeitadas"] = rejeitadas + fundamentos_rejeitados
            payload["resultado"] = "INCONCLUSIVO"
            payload["dados_insuficientes"] = True
            payload["limitacoes"] = list(payload["limitacoes"]) + [
                "Fonte não fornecida no contexto foi rejeitada e não é evidência."
            ]
        payload["requer_revisao_humana"] = True
        return payload

    def _registrar(self, **dados) -> UsoInteligenciaArtificial:
        agora = timezone.now()
        entrada, saida, total = estimar_custo(None, dados["tokens_entrada"], dados["tokens_saida"], agora)
        return UsoInteligenciaArtificial.objects.create(
            provedor=dados["provedor"],
            modelo=None,
            identificador_modelo=dados["modelo"],
            agente="diagnostico_sintetico",
            iniciada_em=dados["iniciada"],
            finalizada_em=agora,
            duracao_ms=dados["duracao"],
            tokens_entrada=dados["tokens_entrada"],
            tokens_saida=dados["tokens_saida"],
            tokens_total=dados["tokens_entrada"] + dados["tokens_saida"],
            custo_estimado_entrada=entrada,
            custo_estimado_saida=saida,
            custo_estimado_total=total,
            status=dados["status"],
            erro_normalizado=dados["erro"],
            id_requisicao_provedor=dados["id_requisicao"][:120],
            fallback_utilizado=False,
            tentativa=1,
            chave_idempotencia=chave_idempotencia("diagnostico-sintetico", dados["provedor"], dados["iniciada"].isoformat()),
            laboratorio=True,
            resposta_estruturada=dados["payload"],
        )
