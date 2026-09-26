from django.db import models


class Rastreavel(models.Model):
    """Marca registros de demonstração e guarda criação e atualização."""

    demonstracao = models.BooleanField("dado de demonstração", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class Entidade(Rastreavel):
    """Organização participante: concedente, beneficiário, fornecedor ou outro."""

    class Tipo(models.TextChoices):
        CONCEDENTE = "concedente", "Concedente"
        BENEFICIARIO = "beneficiario", "Beneficiário"
        FORNECEDOR = "fornecedor", "Fornecedor"
        OUTRO = "outro", "Outro"

    nome = models.CharField("nome", max_length=255)
    nome_fantasia = models.CharField("nome fantasia", max_length=255, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, default=Tipo.OUTRO)
    municipio = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)

    class Meta:
        verbose_name = "entidade"
        verbose_name_plural = "entidades"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["cnpj"],
                condition=~models.Q(cnpj=""),
                name="entidade_cnpj_unico_quando_informado",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class Pessoa(Rastreavel):
    """Pessoa física. Dados funcionais ficam no vínculo, não aqui duplicados."""

    nome = models.CharField("nome", max_length=255)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["cpf"],
                condition=~models.Q(cpf=""),
                name="pessoa_cpf_unico_quando_informado",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class Funcionario(Rastreavel):
    """Vínculo de uma pessoa com uma entidade, para análise futura de folha."""

    class Situacao(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        AFASTADO = "afastado", "Afastado"
        DESLIGADO = "desligado", "Desligado"
        NAO_INFORMADA = "nao_informada", "Não informada"

    pessoa = models.ForeignKey(Pessoa, verbose_name="pessoa", on_delete=models.PROTECT, related_name="vinculos")
    entidade = models.ForeignKey(
        Entidade,
        verbose_name="entidade",
        on_delete=models.PROTECT,
        related_name="funcionarios",
    )
    matricula = models.CharField("matrícula", max_length=40, blank=True)
    cargo = models.CharField("cargo", max_length=120, blank=True)
    data_admissao = models.DateField("data de admissão", null=True, blank=True)
    data_desligamento = models.DateField("data de desligamento", null=True, blank=True)
    carga_horaria = models.DecimalField("carga horária", max_digits=6, decimal_places=2, null=True, blank=True)
    remuneracao_base = models.DecimalField(
        "remuneração base",
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    situacao = models.CharField(
        "situação",
        max_length=20,
        choices=Situacao.choices,
        default=Situacao.NAO_INFORMADA,
    )

    class Meta:
        verbose_name = "funcionário"
        verbose_name_plural = "funcionários"
        ordering = ["pessoa__nome"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(remuneracao_base__isnull=True) | models.Q(remuneracao_base__gte=0),
                name="funcionario_remuneracao_nao_negativa",
            ),
            models.CheckConstraint(
                condition=models.Q(data_admissao__isnull=True)
                | models.Q(data_desligamento__isnull=True)
                | models.Q(data_desligamento__gte=models.F("data_admissao")),
                name="funcionario_datas_coerentes",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa} — {self.entidade}"


class Fornecedor(Rastreavel):
    """Papel de fornecedor de uma entidade, sem repetir o cadastro da organização."""

    entidade = models.OneToOneField(Entidade, verbose_name="entidade", on_delete=models.PROTECT, related_name="fornecedor")
    inscricao_estadual = models.CharField("inscrição estadual", max_length=30, blank=True)
    ramo = models.CharField("ramo", max_length=120, blank=True)

    class Meta:
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"

    def __str__(self) -> str:
        return self.entidade.nome
