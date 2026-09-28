import hashlib
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from aplicacao.inteligencia_artificial.escolhas import (
    EscopoLimite,
    FinalidadeModelo,
    ProvedorIA,
    StatusUso,
    StatusVersaoPrompt,
    UnidadePrecificacao,
)


class ModeloInteligenciaArtificial(models.Model):
    provedor = models.CharField("provedor", max_length=20, choices=ProvedorIA.choices)
    identificador_modelo = models.CharField("identificador do modelo", max_length=120)
    nome_exibicao = models.CharField("nome de exibição", max_length=160)
    finalidade = models.CharField("finalidade", max_length=40, choices=FinalidadeModelo.choices, default=FinalidadeModelo.GERAL)
    ativo = models.BooleanField("ativo", default=True)
    modelo_padrao = models.BooleanField("modelo padrão", default=False)
    suporta_saida_estruturada = models.BooleanField("suporta saída estruturada", default=True)
    limite_contexto = models.PositiveIntegerField("limite de contexto", null=True, blank=True)
    observacoes = models.TextField("observações", blank=True)
    vigencia_inicio = models.DateField("início de vigência", null=True, blank=True)
    vigencia_fim = models.DateField("fim de vigência", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "modelo de inteligência artificial"
        verbose_name_plural = "modelos de inteligência artificial"
        ordering = ["provedor", "nome_exibicao"]
        constraints = [
            models.UniqueConstraint(fields=["provedor", "identificador_modelo"], name="modelo_ia_identificador_unico"),
            models.UniqueConstraint(
                fields=["provedor"],
                condition=models.Q(modelo_padrao=True),
                name="modelo_ia_padrao_por_provedor",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_provedor_display()} · {self.nome_exibicao}"


class PrecoModeloInteligenciaArtificial(models.Model):
    modelo = models.ForeignKey(
        ModeloInteligenciaArtificial,
        verbose_name="modelo",
        on_delete=models.PROTECT,
        related_name="precos",
    )
    vigencia_inicio = models.DateField("início de vigência")
    vigencia_fim = models.DateField("fim de vigência", null=True, blank=True)
    preco_entrada = models.DecimalField("preço de entrada", max_digits=16, decimal_places=6)
    preco_saida = models.DecimalField("preço de saída", max_digits=16, decimal_places=6)
    unidade_precificacao = models.CharField(
        "unidade de precificação",
        max_length=20,
        choices=UnidadePrecificacao.choices,
        default=UnidadePrecificacao.MILHAO_TOKENS,
    )
    moeda = models.CharField("moeda", max_length=8, default="USD")
    fonte_referencia = models.CharField("fonte ou referência administrativa", max_length=255, blank=True)
    observacao = models.TextField("observação", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "preço de modelo"
        verbose_name_plural = "preços de modelo"
        ordering = ["-vigencia_inicio"]

    def __str__(self) -> str:
        return f"{self.modelo} · {self.vigencia_inicio}"


class PromptInteligenciaArtificial(models.Model):
    codigo = models.SlugField("código", max_length=80, unique=True)
    nome = models.CharField("nome", max_length=160)
    agente = models.CharField("agente", max_length=80)
    finalidade = models.CharField("finalidade", max_length=160)

    class Meta:
        verbose_name = "prompt"
        verbose_name_plural = "prompts"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return self.codigo


class VersaoPromptInteligenciaArtificial(models.Model):
    prompt = models.ForeignKey(
        PromptInteligenciaArtificial,
        verbose_name="prompt",
        on_delete=models.PROTECT,
        related_name="versoes",
    )
    versao = models.PositiveIntegerField("versão")
    prompt_sistema = models.TextField("prompt de sistema")
    template_entrada = models.TextField("template de entrada")
    schema_saida = models.JSONField("schema de saída", default=dict)
    ativo = models.BooleanField("ativo", default=True)
    utilizada = models.BooleanField("utilizada", default=False)
    status = models.CharField(
        "status",
        max_length=20,
        choices=StatusVersaoPrompt.choices,
        default=StatusVersaoPrompt.ATIVO,
    )
    tipo_documental = models.CharField("tipo documental", max_length=40, blank=True)
    justificativa = models.TextField("justificativa", blank=True)
    hash_conteudo = models.CharField("hash do conteúdo", max_length=64, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="versoes_prompt_criadas",
    )

    class Meta:
        verbose_name = "versão de prompt"
        verbose_name_plural = "versões de prompt"
        ordering = ["prompt", "-versao"]
        constraints = [
            models.UniqueConstraint(fields=["prompt", "versao"], name="versao_prompt_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.prompt.codigo} v{self.versao}"

    def conteudo_alterado(self, anterior) -> bool:
        return (
            anterior.prompt_sistema != self.prompt_sistema
            or anterior.template_entrada != self.template_entrada
            or anterior.schema_saida != self.schema_saida
        )

    def calcular_hash(self) -> str:
        bruto = json.dumps(
            {
                "schema": self.schema_saida,
                "sistema": self.prompt_sistema,
                "entrada": self.template_entrada,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            anterior = VersaoPromptInteligenciaArtificial.objects.get(pk=self.pk)
            alterou = self.conteudo_alterado(anterior)
            congelada = anterior.utilizada or anterior.status in {
                StatusVersaoPrompt.ATIVO,
                StatusVersaoPrompt.APROVADO,
                StatusVersaoPrompt.SUBSTITUIDO,
                StatusVersaoPrompt.INATIVO,
            }
            if alterou and congelada:
                raise ValidationError("Versão de prompt ativa ou já fechada não pode ser alterada. Crie uma nova versão.")
        self.hash_conteudo = self.calcular_hash()
        super().save(*args, **kwargs)


class UsoInteligenciaArtificial(models.Model):
    provedor = models.CharField("provedor", max_length=20, choices=ProvedorIA.choices)
    modelo = models.ForeignKey(
        ModeloInteligenciaArtificial,
        verbose_name="modelo",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usos",
    )
    identificador_modelo = models.CharField("identificador do modelo", max_length=120, blank=True)
    agente = models.CharField("agente", max_length=80)
    regra = models.ForeignKey(
        "regras.RegraAnalise",
        verbose_name="regra",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usos_ia",
    )
    execucao_analise = models.ForeignKey(
        "regras.ExecucaoAnalise",
        verbose_name="execução da análise",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usos_ia",
    )
    execucao_regra = models.ForeignKey(
        "regras.ExecucaoRegra",
        verbose_name="execução da regra",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usos_ia",
    )
    prestacao_contas = models.ForeignKey(
        "prestacoes_contas.PrestacaoContas",
        verbose_name="prestação de contas",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usos_ia",
    )
    iniciada_em = models.DateTimeField("iniciada em")
    finalizada_em = models.DateTimeField("finalizada em", null=True, blank=True)
    duracao_ms = models.PositiveIntegerField("duração em milissegundos", default=0)
    tokens_entrada = models.PositiveIntegerField("tokens de entrada", default=0)
    tokens_saida = models.PositiveIntegerField("tokens de saída", default=0)
    tokens_total = models.PositiveIntegerField("tokens totais", default=0)
    custo_estimado_entrada = models.DecimalField("custo estimado de entrada", max_digits=16, decimal_places=6, null=True, blank=True)
    custo_estimado_saida = models.DecimalField("custo estimado de saída", max_digits=16, decimal_places=6, null=True, blank=True)
    custo_estimado_total = models.DecimalField("custo estimado total", max_digits=16, decimal_places=6, null=True, blank=True)
    status = models.CharField("status", max_length=30, choices=StatusUso.choices)
    erro_normalizado = models.CharField("erro normalizado", max_length=40, blank=True)
    id_requisicao_provedor = models.CharField("id da requisição no provedor", max_length=120, blank=True)
    versao_prompt = models.ForeignKey(
        VersaoPromptInteligenciaArtificial,
        verbose_name="versão do prompt",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usos",
    )
    fallback_utilizado = models.BooleanField("fallback utilizado", default=False)
    tentativa = models.PositiveIntegerField("tentativa", default=1)
    chave_idempotencia = models.CharField("chave de idempotência", max_length=64, unique=True)
    laboratorio = models.BooleanField("laboratório", default=False)
    resposta_estruturada = models.JSONField("resposta estruturada", default=dict, blank=True)
    provedor_original = models.CharField("provedor original", max_length=20, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "uso de inteligência artificial"
        verbose_name_plural = "usos de inteligência artificial"
        ordering = ["-iniciada_em"]

    def __str__(self) -> str:
        return f"{self.agente} · {self.provedor} · {self.status}"


class LimiteConsumoInteligenciaArtificial(models.Model):
    escopo = models.CharField("escopo", max_length=20, choices=EscopoLimite.choices, default=EscopoLimite.CHAMADA)
    provedor = models.CharField("provedor", max_length=20, choices=ProvedorIA.choices, blank=True)
    max_caracteres_contexto = models.PositiveIntegerField("máximo de caracteres de contexto", default=12000)
    max_tentativas = models.PositiveIntegerField("máximo de tentativas", default=2)
    ativo = models.BooleanField("ativo", default=True)
    observacao = models.TextField("observação", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "limite de consumo"
        verbose_name_plural = "limites de consumo"

    def __str__(self) -> str:
        return f"{self.get_escopo_display()} · {self.max_tentativas} tentativas"


class ConfiguracaoRoteamento(models.Model):
    nome = models.CharField("nome", max_length=80, default="principal")
    provedor_principal = models.CharField("provedor principal", max_length=20, choices=ProvedorIA.choices)
    modelo_principal = models.ForeignKey(
        ModeloInteligenciaArtificial,
        verbose_name="modelo principal",
        on_delete=models.PROTECT,
        related_name="roteamentos_principais",
    )
    provedor_fallback = models.CharField("provedor de fallback", max_length=20, choices=ProvedorIA.choices, blank=True)
    modelo_fallback = models.ForeignKey(
        ModeloInteligenciaArtificial,
        verbose_name="modelo de fallback",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="roteamentos_fallback",
    )
    ativo = models.BooleanField("ativo", default=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "configuração de roteamento"
        verbose_name_plural = "configurações de roteamento"

    def __str__(self) -> str:
        return self.nome


class EventoOperacionalProvedor(models.Model):
    provedor = models.CharField("provedor", max_length=20, choices=ProvedorIA.choices)
    erro_normalizado = models.CharField("erro normalizado", max_length=40)
    ocorrido_em = models.DateTimeField("ocorrido em", auto_now_add=True)

    class Meta:
        verbose_name = "evento operacional de provedor"
        verbose_name_plural = "eventos operacionais de provedor"
        ordering = ["-ocorrido_em"]

    def __str__(self) -> str:
        return f"{self.provedor} · {self.erro_normalizado}"
