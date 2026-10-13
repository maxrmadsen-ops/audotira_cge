from django import forms

from aplicacao.diligencias.escolhas import MotivoDiligencia
from aplicacao.documentos.models import Documento


class FormularioNovaDiligencia(forms.Form):
    motivo = forms.ChoiceField(label="Motivo/categoria", choices=MotivoDiligencia.choices)
    descricao = forms.CharField(label="Descrição", widget=forms.Textarea(attrs={"rows": 4}))
    prazo = forms.DateField(label="Prazo", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    documentos = forms.ModelMultipleChoiceField(
        label="Documentos relacionados",
        queryset=Documento.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["documentos"].queryset = Documento.objects.ativos().filter(prestacao_contas=prestacao)


class FormularioRespostaDiligencia(forms.Form):
    resposta = forms.CharField(
        label="Resposta/manifestação recebida",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Registre apenas a manifestação efetivamente recebida. O sistema não inventa resposta.",
    )


class FormularioEncerrarDiligencia(forms.Form):
    observacao = forms.CharField(
        label="Observação de encerramento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
