import hashlib
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from aplicacao.instrumentos.escolhas import (
    CategoriaClausula,
    CategoriaObrigacao,
    OperadorTemporal,
    PapelParte,
    SituacaoExpectativa,
    StatusCampo,
    StatusCorrespondenciaNorma,
    StatusValidacaoTermo,
    UnidadeTemporal,
)


class TermoCongelado(ValidationError):
    pass


class TermoFomento(models.Model):
    """Leitura estruturada de um termo. O documento continua sendo a fonte."""

    documento = models.OneToOneField(
        "documentos.Documento",
        verbose_name="documento",
        on_delete=models.CASCADE,
        related_name="termo_fomento",
    )
    versao_prompt = models.ForeignKey(
        "inteligencia_artificial.VersaoPromptInteligenciaArtificial",
        verbose_name="versão do prompt",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="termos",
    )
    tipo_instrumento = models.CharField("tipo do instrumento", max_length=80, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    ano = models.PositiveIntegerField("ano", null=True, blank=True)
    identificacao_completa = models.CharField("identificação completa", max_length=160, blank=True)
    processo_sgpe = models.CharField("processo SGPe", max_length=80, blank=True)
    municipio = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    data_celebracao = models.DateField("data de celebração", null=True, blank=True)
    data_assinatura = models.DateField("data de assinatura", null=True, blank=True)
    data_publicacao = models.DateField("data de publicação", null=True, blank=True)
    vigencia_inicio = models.DateField("início da vigência", null=True, blank=True)
    vigencia_fim = models.DateField("fim da vigência", null=True, blank=True)
    duracao_texto = models.CharField("duração", max_length=160, blank=True)
    objeto_integral = models.TextField("objeto", blank=True)
    objeto_resumo = models.TextField("resumo do objeto", blank=True)
    finalidade = models.TextField("finalidade", blank=True)
    publico_alvo = models.TextField("público-alvo", blank=True)
    local_execucao = models.CharField("local de execução", max_length=255, blank=True)
    referencia_plano_trabalho = models.CharField("referência ao plano de trabalho", max_length=255, blank=True)
    politicas_publicas = models.TextField("políticas públicas", blank=True)
    restricoes_uso = models.TextField("restrições de uso", blank=True)
    destinacao_recursos = models.TextField("destinação dos recursos", blank=True)
    moeda = models.CharField("moeda", max_length=8, blank=True)
    valor_total = models.DecimalField("valor total", max_digits=16, decimal_places=2, null=True, blank=True)
    valor_total_texto = models.CharField("valor total no documento", max_length=80, blank=True)
    quantidade_parcelas = models.PositiveIntegerField("quantidade de parcelas", null=True, blank=True)
    valor_parcela = models.DecimalField("valor da parcela", max_digits=16, decimal_places=2, null=True, blank=True)
    valor_parcela_texto = models.CharField("valor da parcela no documento", max_length=80, blank=True)
    consistente_aritmeticamente = models.BooleanField("consistência aritmética", null=True, blank=True)
    alerta_aritmetico = models.TextField("alerta de validação aritmética", blank=True)
    metodo_extracao = models.CharField("método de extração", max_length=40, blank=True)
    status_validacao = models.CharField(
        "status da validação",
        max_length=40,
        choices=StatusValidacaoTermo.choices,
        default=StatusValidacaoTermo.AGUARDANDO_VALIDACAO,
    )
    versao = models.PositiveIntegerField("versão", default=1)
    congelado = models.BooleanField("congelado", default=False)
    hash_congelado = models.CharField("hash da versão congelada", max_length=64, blank=True)
    congelado_em = models.DateTimeField("congelado em", null=True, blank=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="termos_validados",
    )
    validado_em = models.DateTimeField("validado em", null=True, blank=True)
    demonstracao = models.BooleanField("dado de demonstração", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "termo de fomento"
        verbose_name_plural = "termos de fomento"

    def __str__(self) -> str:
        return self.identificacao_completa or f"Termo do documento {self.documento_id}"

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_liberar_congelamento", False):
            anterior = TermoFomento.objects.get(pk=self.pk)
            if anterior.congelado:
                raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
        super().save(*args, **kwargs)

    def conteudo_canonico(self) -> dict:
        campos = [
            {
                "nome": campo.nome,
                "extraido": campo.valor_extraido,
                "validado": campo.valor_validado,
                "status": campo.status,
            }
            for campo in self.campos.order_by("nome")
        ]
        return {"versao": self.versao, "campos": campos}

    def calcular_hash(self) -> str:
        bruto = json.dumps(self.conteudo_canonico(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


class VersaoTermoCongelada(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="versoes_congeladas")
    numero = models.PositiveIntegerField("número")
    hash_conteudo = models.CharField("hash", max_length=64)
    conteudo = models.JSONField("conteúdo", default=dict)
    congelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="congelado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="versoes_termo_congeladas",
    )
    congelado_em = models.DateTimeField("congelado em", auto_now_add=True)

    class Meta:
        verbose_name = "versão congelada do termo"
        verbose_name_plural = "versões congeladas do termo"
        constraints = [
            models.UniqueConstraint(fields=["termo", "numero"], name="versao_termo_congelada_unica"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise TermoCongelado("Versão congelada é imutável.")
        super().save(*args, **kwargs)


class ParteInstrumento(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="partes")
    papel = models.CharField("papel", max_length=20, choices=PapelParte.choices)
    nome = models.TextField("nome", blank=True)
    sigla = models.CharField("sigla", max_length=40, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    endereco = models.TextField("endereço", blank=True)
    municipio = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    representante_nome = models.CharField("representante", max_length=255, blank=True)
    representante_cargo = models.CharField("cargo do representante", max_length=160, blank=True)
    representante_cpf = models.CharField("CPF do representante", max_length=14, blank=True)

    class Meta:
        verbose_name = "parte do instrumento"
        verbose_name_plural = "partes do instrumento"
        constraints = [
            models.UniqueConstraint(fields=["termo", "papel"], name="parte_unica_por_papel"),
        ]


class ClausulaInstrumento(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="clausulas")
    numero = models.PositiveIntegerField("número", null=True, blank=True)
    ordinal = models.CharField("ordinal", max_length=40, blank=True)
    titulo = models.CharField("título", max_length=255, blank=True)
    texto = models.TextField("texto", blank=True)
    pagina = models.PositiveIntegerField("página", null=True, blank=True)
    posicao = models.PositiveIntegerField("posição", default=0)
    categoria = models.CharField(
        "categoria",
        max_length=40,
        choices=CategoriaClausula.choices,
        default=CategoriaClausula.OUTRA,
    )

    class Meta:
        verbose_name = "cláusula"
        verbose_name_plural = "cláusulas"
        ordering = ["posicao", "numero"]


class ObrigacaoInstrumento(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="obrigacoes")
    clausula = models.ForeignKey(
        ClausulaInstrumento,
        verbose_name="cláusula",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="obrigacoes",
    )
    sujeito = models.CharField("sujeito", max_length=160, blank=True)
    texto = models.TextField("texto", blank=True)
    categoria = models.CharField(
        "categoria",
        max_length=40,
        choices=CategoriaObrigacao.choices,
        default=CategoriaObrigacao.OUTRA,
    )
    condicao = models.TextField("condição", blank=True)
    prazo_texto = models.CharField("prazo", max_length=255, blank=True)
    evidencia_esperada = models.CharField("evidência esperada", max_length=160, blank=True)
    verificavel_futuramente = models.BooleanField("verificável futuramente", default=True)
    situacao = models.CharField(
        "situação",
        max_length=30,
        choices=SituacaoExpectativa.choices,
        default=SituacaoExpectativa.NAO_VERIFICAVEL,
    )

    class Meta:
        verbose_name = "obrigação do instrumento"
        verbose_name_plural = "obrigações do instrumento"


class RegraTemporal(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="regras_temporais")
    clausula = models.ForeignKey(
        ClausulaInstrumento,
        verbose_name="cláusula",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="regras_temporais",
    )
    evento_origem = models.CharField("evento de origem", max_length=160, blank=True)
    quantidade = models.PositiveIntegerField("quantidade", null=True, blank=True)
    unidade = models.CharField("unidade", max_length=20, choices=UnidadeTemporal.choices, blank=True)
    operador = models.CharField("operador", max_length=20, choices=OperadorTemporal.choices, blank=True)
    evento_destino = models.CharField("evento de destino", max_length=160, blank=True)
    condicao = models.TextField("condição", blank=True)
    data_documental = models.DateField("data documental", null=True, blank=True)
    data_calculada = models.DateField("data calculada", null=True, blank=True)
    calculo = models.CharField("cálculo", max_length=255, blank=True)
    trecho = models.TextField("trecho", blank=True)
    pagina = models.PositiveIntegerField("página", null=True, blank=True)

    class Meta:
        verbose_name = "regra temporal"
        verbose_name_plural = "regras temporais"


class AplicacaoFinanceiraEsperada(models.Model):
    termo = models.OneToOneField(
        TermoFomento,
        verbose_name="termo",
        on_delete=models.CASCADE,
        related_name="aplicacao_financeira",
    )
    clausula = models.ForeignKey(
        ClausulaInstrumento,
        verbose_name="cláusula",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aplicacoes_financeiras",
    )
    texto = models.TextField("obrigação", blank=True)
    sujeito = models.CharField("sujeito", max_length=160, blank=True)
    condicao = models.TextField("condição", blank=True)
    destinacao_rendimentos = models.TextField("destinação dos rendimentos", blank=True)
    evidencia_esperada = models.CharField("evidência esperada", max_length=160, blank=True)
    situacao = models.CharField(
        "situação",
        max_length=30,
        choices=SituacaoExpectativa.choices,
        default=SituacaoExpectativa.NAO_VERIFICAVEL,
    )

    class Meta:
        verbose_name = "aplicação financeira esperada"
        verbose_name_plural = "aplicações financeiras esperadas"


class ContaBancariaEsperada(models.Model):
    termo = models.OneToOneField(
        TermoFomento,
        verbose_name="termo",
        on_delete=models.CASCADE,
        related_name="conta_bancaria",
    )
    clausula = models.ForeignKey(
        ClausulaInstrumento,
        verbose_name="cláusula",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contas_bancarias",
    )
    instituicao = models.CharField("instituição financeira", max_length=160, blank=True)
    tipo_conta = models.CharField("tipo de conta", max_length=80, blank=True)
    agencia = models.CharField("agência", max_length=20, blank=True)
    numero_conta = models.CharField("número da conta", max_length=30, blank=True)
    texto = models.TextField("obrigação", blank=True)
    evidencia_esperada = models.CharField("evidência esperada", max_length=160, blank=True)

    class Meta:
        verbose_name = "conta bancária esperada"
        verbose_name_plural = "contas bancárias esperadas"


class ReferenciaNormativaExtraida(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="referencias_normativas")
    clausula = models.ForeignKey(
        ClausulaInstrumento,
        verbose_name="cláusula",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referencias_normativas",
    )
    norma = models.ForeignKey(
        "normas.Norma",
        verbose_name="norma do catálogo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referencias_extraidas",
    )
    tipo = models.CharField("tipo", max_length=40, blank=True)
    numero = models.CharField("número", max_length=40, blank=True)
    ano = models.CharField("ano", max_length=8, blank=True)
    esfera = models.CharField("esfera", max_length=40, blank=True)
    texto = models.CharField("texto da referência", max_length=255)
    trecho = models.TextField("trecho", blank=True)
    pagina = models.PositiveIntegerField("página", null=True, blank=True)
    status_correspondencia = models.CharField(
        "status da correspondência",
        max_length=30,
        choices=StatusCorrespondenciaNorma.choices,
        default=StatusCorrespondenciaNorma.NAO_CONFRONTADA,
    )

    class Meta:
        verbose_name = "referência normativa extraída"
        verbose_name_plural = "referências normativas extraídas"


class ConsequenciaInstrumento(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="consequencias")
    clausula = models.ForeignKey(
        ClausulaInstrumento,
        verbose_name="cláusula",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consequencias",
    )
    texto = models.TextField("texto", blank=True)
    percentual = models.DecimalField("percentual", max_digits=6, decimal_places=2, null=True, blank=True)
    valor = models.DecimalField("valor", max_digits=16, decimal_places=2, null=True, blank=True)
    trecho = models.TextField("trecho", blank=True)
    pagina = models.PositiveIntegerField("página", null=True, blank=True)

    class Meta:
        verbose_name = "consequência do instrumento"
        verbose_name_plural = "consequências do instrumento"


class RegraDerivadaInstrumento(models.Model):
    """Regra particular do instrumento. Não entra no catálogo das regras CGE."""

    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="regras_derivadas")
    obrigacao = models.ForeignKey(
        ObrigacaoInstrumento,
        verbose_name="obrigação",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="regras_derivadas",
    )
    codigo = models.CharField("código", max_length=40)
    descricao = models.TextField("descrição")
    conclusao = models.CharField("conclusão", max_length=40, blank=True)

    class Meta:
        verbose_name = "regra derivada do instrumento"
        verbose_name_plural = "regras derivadas do instrumento"


class CampoInstrumento(models.Model):
    termo = models.ForeignKey(TermoFomento, verbose_name="termo", on_delete=models.CASCADE, related_name="campos")
    nome = models.CharField("campo", max_length=80)
    rotulo = models.CharField("rótulo", max_length=120)
    valor_extraido = models.TextField("valor extraído", blank=True)
    valor_validado = models.TextField("valor validado", blank=True)
    status = models.CharField("status", max_length=30, choices=StatusCampo.choices, default=StatusCampo.AGUARDANDO)
    pagina = models.PositiveIntegerField("página", null=True, blank=True)
    trecho = models.TextField("trecho", blank=True)
    metodo = models.CharField("método", max_length=40, blank=True)
    observacao = models.TextField("observação", blank=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campos_instrumento_validados",
    )
    validado_em = models.DateTimeField("validado em", null=True, blank=True)

    class Meta:
        verbose_name = "campo do instrumento"
        verbose_name_plural = "campos do instrumento"
        constraints = [
            models.UniqueConstraint(fields=["termo", "nome"], name="campo_instrumento_unico"),
        ]
        ordering = ["nome"]

    def save(self, *args, **kwargs):
        if self.termo_id and self.termo.congelado and not getattr(self, "_liberar_congelamento", False):
            raise TermoCongelado("Versão congelada não pode ser alterada. Abra uma nova versão.")
        super().save(*args, **kwargs)
