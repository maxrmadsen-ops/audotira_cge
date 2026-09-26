from django import forms

from aplicacao.normas.models import AplicabilidadeNorma, Norma, RelacionamentoNorma
from aplicacao.prestacoes_contas.models import PrestacaoContas


def _estilizar(formulario: forms.BaseForm) -> None:
    for campo in formulario.fields.values():
        if not isinstance(campo.widget, (forms.CheckboxInput, forms.FileInput)):
            campo.widget.attrs.setdefault("class", "form-control")
        elif isinstance(campo.widget, forms.FileInput):
            campo.widget.attrs.setdefault("class", "form-control")


class FormularioNorma(forms.ModelForm):
    arquivo = forms.FileField(label="Fonte em PDF", required=False)

    class Meta:
        model = Norma
        fields = [
            "tipo_norma",
            "numero",
            "ano",
            "titulo",
            "ementa",
            "orgao_emissor",
            "esfera",
            "data_publicacao",
            "inicio_vigencia",
            "fim_vigencia",
            "situacao",
            "fonte",
            "observacoes",
        ]

    def __init__(self, *args, exigir_arquivo: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["arquivo"].required = exigir_arquivo
        self.fields["inicio_vigencia"].required = True
        for nome in ("data_publicacao", "inicio_vigencia", "fim_vigencia"):
            self.fields[nome].widget.input_type = "date"
        _estilizar(self)

    def clean(self):
        dados = super().clean()
        inicio = dados.get("inicio_vigencia")
        fim = dados.get("fim_vigencia")
        if inicio and fim and fim < inicio:
            self.add_error("fim_vigencia", "O fim da vigência não pode ser anterior ao início.")
        return dados


class FormularioAplicabilidade(forms.ModelForm):
    class Meta:
        model = AplicabilidadeNorma
        fields = [
            "tipo_instrumento",
            "orgao",
            "tipo_prestacao",
            "periodo_inicio",
            "periodo_fim",
            "categoria",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("periodo_inicio", "periodo_fim"):
            self.fields[nome].widget.input_type = "date"
        _estilizar(self)


class FormularioRelacionamento(forms.ModelForm):
    class Meta:
        model = RelacionamentoNorma
        fields = ["destino", "tipo", "observacao"]

    def __init__(self, *args, norma: Norma | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if norma is not None:
            self.fields["destino"].queryset = Norma.objects.exclude(pk=norma.pk)
        _estilizar(self)


class FormularioPesquisaNormativa(forms.Form):
    texto = forms.CharField(label="Consulta", widget=forms.Textarea(attrs={"rows": 3}))
    data_referencia = forms.DateField(label="Data de referência", widget=forms.DateInput(attrs={"type": "date"}))
    tipo_instrumento = forms.CharField(label="Tipo de instrumento", required=False)
    orgao = forms.CharField(label="Órgão", required=False)
    tipo_prestacao = forms.CharField(label="Tipo de prestação", required=False)
    categoria = forms.CharField(label="Categoria", required=False)
    prestacao_contas = forms.ModelChoiceField(
        label="Prestação de contas",
        queryset=PrestacaoContas.objects.none(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prestacao_contas"].queryset = PrestacaoContas.objects.all()
        _estilizar(self)
