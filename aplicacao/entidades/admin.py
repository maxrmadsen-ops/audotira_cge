from django.contrib import admin

from aplicacao.entidades.models import Entidade, Fornecedor, Funcionario, Pessoa


@admin.register(Entidade)
class EntidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "cnpj", "municipio", "demonstracao")
    search_fields = ("nome", "cnpj")
    list_filter = ("tipo", "demonstracao")


@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf", "demonstracao")
    search_fields = ("nome", "cpf")


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("pessoa", "entidade", "cargo", "situacao")
    list_filter = ("situacao",)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("entidade", "ramo")
    search_fields = ("entidade__nome",)
