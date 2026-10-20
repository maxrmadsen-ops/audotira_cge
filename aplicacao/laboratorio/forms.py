from django import forms

from aplicacao.laboratorio.catalogo import escolhas_tipo
from aplicacao.laboratorio.escolhas import EstadoVinculo, PrioridadePendencia, StatusPendencia


class FormularioClassificacaoRegiao(forms.Form):
    tipo_documental = forms.ChoiceField(choices=escolhas_tipo(), label="Tipo documental")
    justificativa = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    x = forms.FloatField(min_value=0, max_value=1, required=False)
    y = forms.FloatField(min_value=0, max_value=1, required=False)
    largura = forms.FloatField(min_value=0.01, max_value=1, required=False)
    altura = forms.FloatField(min_value=0.01, max_value=1, required=False)


class FormularioCampo(forms.Form):
    valor_original = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    acao = forms.ChoiceField(
        choices=(
            ("confirmar", "Confirmar extração"),
            ("corrigir", "Corrigir extração"),
            ("ausente", "Marcar ausente na evidência"),
        )
    )


class FormularioVinculo(forms.Form):
    estado = forms.ChoiceField(choices=EstadoVinculo.choices)
    justificativa = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class FormularioPendencia(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    prioridade = forms.ChoiceField(choices=PrioridadePendencia.choices, initial=PrioridadePendencia.MEDIA)
    solicitacao_esclarecimento = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    status = forms.ChoiceField(choices=StatusPendencia.choices, initial=StatusPendencia.ABERTA)


class FormularioIlegibilidade(forms.Form):
    justificativa = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))


class FormularioReprocessamento(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
