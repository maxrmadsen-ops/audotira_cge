from django import forms

from aplicacao.documentos.escolhas import TipoDocumento
from aplicacao.documentos.models import Documento
from aplicacao.prestacoes_contas.models import PrestacaoParcial


class FormularioValidacao(forms.Form):
    tipo_documento = forms.ChoiceField(label="Tipo", choices=TipoDocumento.choices)
    subtipo_documento = forms.CharField(label="Subtipo", max_length=120, required=False)
    prestacao_parcial = forms.ModelChoiceField(label="Prestação parcial", queryset=PrestacaoParcial.objects.none(), required=False)
    data_documento = forms.DateField(
        label="Data do documento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, documento: Documento | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if documento is not None:
            self.fields["prestacao_parcial"].queryset = documento.prestacao_contas.parciais.all()
            self.fields["tipo_documento"].initial = documento.tipo_documento
            self.fields["subtipo_documento"].initial = documento.subtipo_documento
            self.fields["prestacao_parcial"].initial = documento.prestacao_parcial_id
            self.fields["data_documento"].initial = documento.data_documento
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.Select):
                campo.widget.attrs.setdefault("class", "form-control")
            else:
                campo.widget.attrs.setdefault("class", "form-select")


class FormularioReprocessamento(forms.Form):
    motivo = forms.CharField(label="Motivo", max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo"].widget.attrs.setdefault("class", "form-control")
