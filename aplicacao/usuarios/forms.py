from django.contrib.auth.forms import AuthenticationForm


class FormularioEntrada(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["password"].label = "Senha"
        self.fields["username"].widget.attrs.update({"class": "form-control", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "form-control"})
