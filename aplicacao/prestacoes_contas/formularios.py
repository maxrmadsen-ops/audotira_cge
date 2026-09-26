from django import forms

from aplicacao.entidades.models import Entidade, Fornecedor, Funcionario, Pessoa
from aplicacao.prestacoes_contas.models import (
    Contrapartida,
    Despesa,
    Devolucao,
    DocumentoFiscal,
    Instrumento,
    ItemPlanoTrabalho,
    Meta,
    MovimentacaoBancaria,
    Pagamento,
    PlanoTrabalho,
    PrestacaoContas,
    PrestacaoParcial,
)


def _estilizar(formulario: forms.BaseForm) -> None:
    for campo in formulario.fields.values():
        if not isinstance(campo.widget, (forms.CheckboxInput, forms.RadioSelect)):
            campo.widget.attrs.setdefault("class", "form-control")


class FormularioPrestacao(forms.ModelForm):
    nome_concedente = forms.CharField(label="Novo concedente", required=False)
    nome_beneficiario = forms.CharField(label="Novo beneficiário", required=False)
    numero_instrumento = forms.CharField(label="Número do instrumento", required=False)
    tipo_instrumento = forms.ChoiceField(label="Tipo do instrumento", choices=Instrumento._meta.get_field("tipo").choices, required=False)
    vigencia_inicio = forms.DateField(label="Início da vigência", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    vigencia_fim = forms.DateField(label="Fim da vigência", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    valor_instrumento = forms.DecimalField(label="Valor do instrumento", required=False, max_digits=16, decimal_places=2)

    class Meta:
        model = PrestacaoContas
        fields = [
            "numero_processo",
            "concedente",
            "beneficiario",
            "objeto",
            "valor_total",
            "data_inicio",
            "data_fim",
            "situacao",
            "fase",
        ]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concedente"].required = False
        self.fields["beneficiario"].required = False
        self.fields["concedente"].queryset = Entidade.objects.order_by("nome")
        self.fields["beneficiario"].queryset = Entidade.objects.order_by("nome")
        instrumento = self.instance.instrumento_principal if self.instance.pk else None
        if instrumento:
            self.fields["numero_instrumento"].initial = instrumento.numero
            self.fields["tipo_instrumento"].initial = instrumento.tipo
            self.fields["vigencia_inicio"].initial = instrumento.vigencia_inicio
            self.fields["vigencia_fim"].initial = instrumento.vigencia_fim
            self.fields["valor_instrumento"].initial = instrumento.valor
        _estilizar(self)

    def _entidade(self, nome: str, tipo: str, selecionada: Entidade | None) -> Entidade | None:
        if selecionada:
            return selecionada
        nome = (nome or "").strip()
        if not nome:
            return None
        entidade, _ = Entidade.objects.get_or_create(nome=nome, tipo=tipo, defaults={"demonstracao": False})
        return entidade

    def save(self, commit=True):
        prestacao = super().save(commit=False)
        prestacao.concedente = self._entidade(
            self.cleaned_data.get("nome_concedente", ""),
            Entidade.Tipo.CONCEDENTE,
            self.cleaned_data.get("concedente"),
        )
        prestacao.beneficiario = self._entidade(
            self.cleaned_data.get("nome_beneficiario", ""),
            Entidade.Tipo.BENEFICIARIO,
            self.cleaned_data.get("beneficiario"),
        )
        if commit:
            prestacao.save()
            self._salvar_instrumento(prestacao)
        return prestacao

    def _salvar_instrumento(self, prestacao: PrestacaoContas) -> None:
        numero = self.cleaned_data.get("numero_instrumento", "").strip()
        tipo = self.cleaned_data.get("tipo_instrumento") or ""
        inicio = self.cleaned_data.get("vigencia_inicio")
        fim = self.cleaned_data.get("vigencia_fim")
        valor = self.cleaned_data.get("valor_instrumento")
        if not any([numero, tipo, inicio, fim, valor is not None]):
            return
        instrumento = prestacao.instrumento_principal or Instrumento(prestacao=prestacao, principal=True)
        instrumento.numero = numero
        if tipo:
            instrumento.tipo = tipo
        instrumento.vigencia_inicio = inicio
        instrumento.vigencia_fim = fim
        instrumento.valor = valor
        instrumento.demonstracao = prestacao.demonstracao
        instrumento.save()


class FormularioPlano(forms.ModelForm):
    class Meta:
        model = PlanoTrabalho
        fields = ["titulo", "versao", "vigencia_inicio", "vigencia_fim"]
        widgets = {
            "vigencia_inicio": forms.DateInput(attrs={"type": "date"}),
            "vigencia_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)


class FormularioItemPlano(forms.ModelForm):
    class Meta:
        model = ItemPlanoTrabalho
        fields = ["categoria", "descricao", "quantidade", "unidade", "valor_previsto", "natureza", "periodo_inicio", "periodo_fim"]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, plano=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plano = plano
        _estilizar(self)


class FormularioMeta(forms.ModelForm):
    class Meta:
        model = Meta
        fields = ["codigo", "descricao", "indicador", "quantidade_prevista", "unidade"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)


class FormularioParcial(forms.ModelForm):
    class Meta:
        model = PrestacaoParcial
        fields = ["tipo", "numero_ordem", "periodo_inicio", "periodo_fim", "descricao"]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)


class FormularioDespesa(forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ["descricao", "valor", "data", "categoria", "natureza", "prestacao_parcial", "item_plano", "fornecedor"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["prestacao_parcial"].queryset = prestacao.parciais.all()
            self.fields["item_plano"].queryset = ItemPlanoTrabalho.objects.filter(plano__prestacao=prestacao)
            self.fields["fornecedor"].queryset = Fornecedor.objects.select_related("entidade")
        for nome in ("prestacao_parcial", "item_plano", "fornecedor"):
            self.fields[nome].required = False
        _estilizar(self)


class FormularioDocumentoFiscal(forms.ModelForm):
    despesa = forms.ModelChoiceField(label="Despesa relacionada", queryset=Despesa.objects.none(), required=False)

    class Meta:
        model = DocumentoFiscal
        fields = ["tipo", "numero", "serie", "data_emissao", "valor", "emitente"]
        widgets = {"data_emissao": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["despesa"].queryset = prestacao.despesas.all()
            self.fields["emitente"].queryset = Fornecedor.objects.select_related("entidade")
        self.fields["emitente"].required = False
        _estilizar(self)


class FormularioPagamento(forms.ModelForm):
    class Meta:
        model = Pagamento
        fields = ["data", "valor", "meio", "identificador", "prestacao_parcial", "despesas", "documentos_fiscais"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["prestacao_parcial"].queryset = prestacao.parciais.all()
            self.fields["despesas"].queryset = prestacao.despesas.all()
            self.fields["documentos_fiscais"].queryset = prestacao.documentos_fiscais.all()
        for nome in ("prestacao_parcial", "despesas", "documentos_fiscais", "meio"):
            self.fields[nome].required = False
        _estilizar(self)


class FormularioMovimentacao(forms.ModelForm):
    class Meta:
        model = MovimentacaoBancaria
        fields = ["data", "valor", "tipo", "historico", "identificador", "pagamentos"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["pagamentos"].queryset = prestacao.pagamentos.all()
        self.fields["pagamentos"].required = False
        self.fields["tipo"].required = False
        _estilizar(self)


class FormularioContrapartida(forms.ModelForm):
    class Meta:
        model = Contrapartida
        fields = ["descricao", "valor", "data", "item_plano"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["item_plano"].queryset = ItemPlanoTrabalho.objects.filter(plano__prestacao=prestacao)
        self.fields["item_plano"].required = False
        _estilizar(self)


class FormularioDevolucao(forms.ModelForm):
    class Meta:
        model = Devolucao
        fields = ["data", "valor", "motivo", "prestacao_parcial"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, prestacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if prestacao is not None:
            self.fields["prestacao_parcial"].queryset = prestacao.parciais.all()
        self.fields["prestacao_parcial"].required = False
        _estilizar(self)


class FormularioFuncionario(forms.Form):
    nome = forms.CharField(label="Nome", max_length=255)
    cpf = forms.CharField(label="CPF", max_length=14, required=False)
    cargo = forms.CharField(label="Cargo", max_length=120, required=False)
    remuneracao_base = forms.DecimalField(label="Remuneração base", max_digits=16, decimal_places=2, required=False)
    data_admissao = forms.DateField(label="Admissão", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)

    def criar(self, entidade: Entidade, demonstracao: bool = False) -> Funcionario:
        pessoa = Pessoa.objects.create(nome=self.cleaned_data["nome"], cpf=self.cleaned_data.get("cpf", ""), demonstracao=demonstracao)
        return Funcionario.objects.create(
            pessoa=pessoa,
            entidade=entidade,
            cargo=self.cleaned_data.get("cargo", ""),
            remuneracao_base=self.cleaned_data.get("remuneracao_base"),
            data_admissao=self.cleaned_data.get("data_admissao"),
            demonstracao=demonstracao,
        )
