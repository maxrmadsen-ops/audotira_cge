from django.contrib import admin

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


@admin.register(PrestacaoContas)
class PrestacaoContasAdmin(admin.ModelAdmin):
    list_display = ("numero_processo", "concedente", "beneficiario", "situacao", "fase", "demonstracao")
    search_fields = ("numero_processo", "objeto", "concedente__nome", "beneficiario__nome")
    list_filter = ("situacao", "fase", "demonstracao")


@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ("numero", "tipo", "prestacao", "principal")
    list_filter = ("tipo", "principal")


@admin.register(PlanoTrabalho)
class PlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "versao", "prestacao")


@admin.register(ItemPlanoTrabalho)
class ItemPlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "natureza", "valor_previsto", "plano")


@admin.register(Meta)
class MetaAdmin(admin.ModelAdmin):
    list_display = ("descricao", "plano")


@admin.register(PrestacaoParcial)
class PrestacaoParcialAdmin(admin.ModelAdmin):
    list_display = ("__str__", "numero_ordem", "tipo", "prestacao")


@admin.register(Despesa)
class DespesaAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "data", "prestacao")


@admin.register(DocumentoFiscal)
class DocumentoFiscalAdmin(admin.ModelAdmin):
    list_display = ("tipo", "numero", "valor", "prestacao")


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ("identificador", "valor", "data", "meio")


@admin.register(MovimentacaoBancaria)
class MovimentacaoBancariaAdmin(admin.ModelAdmin):
    list_display = ("historico", "tipo", "valor", "data")


@admin.register(Contrapartida)
class ContrapartidaAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "prestacao")


@admin.register(Devolucao)
class DevolucaoAdmin(admin.ModelAdmin):
    list_display = ("motivo", "valor", "data", "prestacao")
