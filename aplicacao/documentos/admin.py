from django.contrib import admin

from aplicacao.documentos.models import DadoExtraidoDocumento, Documento, PaginaDocumento, ReprocessamentoDocumento


class PaginaInline(admin.TabularInline):
    model = PaginaDocumento
    extra = 0
    fields = ("numero_pagina", "metodo_extracao", "qualidade_extracao", "necessitou_ocr", "ocr_executado", "quantidade_caracteres")
    readonly_fields = fields
    can_delete = False


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nome_original", "prestacao_contas", "tipo_documento", "status_processamento", "hash_sha256")
    search_fields = ("nome_original", "hash_sha256")
    list_filter = ("status_processamento", "tipo_documento", "demonstracao")
    readonly_fields = ("nome_armazenado", "hash_sha256", "tamanho_bytes", "erro_processamento")
    inlines = [PaginaInline]


@admin.register(DadoExtraidoDocumento)
class DadoExtraidoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "valor", "documento", "metodo")
    readonly_fields = ("trecho",)


@admin.register(ReprocessamentoDocumento)
class ReprocessamentoAdmin(admin.ModelAdmin):
    list_display = ("documento", "solicitado_por", "solicitado_em", "resultado")
