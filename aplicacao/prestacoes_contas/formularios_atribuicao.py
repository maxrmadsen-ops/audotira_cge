from django import forms

from aplicacao.usuarios.models import Usuario


class FormularioAtribuicaoAnalista(forms.Form):
    analista = forms.ModelChoiceField(
        label="Analista responsável",
        queryset=Usuario.objects.none(),
        required=False,
        empty_label="Sem analista responsável",
    )
    justificativa = forms.CharField(
        label="Justificativa",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["analista"].queryset = Usuario.objects.filter(
            perfil=Usuario.Perfil.ANALISTA,
            is_active=True,
        ).order_by("username")
