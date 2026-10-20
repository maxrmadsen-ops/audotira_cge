from django.contrib import admin

from aplicacao.laboratorio import models


@admin.register(models.LoteLaboratorio)
class LoteLaboratorioAdmin(admin.ModelAdmin):
    list_display = ("id", "numero_processo_parcial", "hash_sha256", "quantidade_paginas", "importado_em")
    search_fields = ("numero_processo_parcial", "hash_sha256", "numero_instrumento")
    readonly_fields = ("hash_sha256", "tamanho_bytes", "importado_em")


admin.site.register(models.InventarioPagina)
admin.site.register(models.RegiaoDocumental)
admin.site.register(models.CampoExtraido)
admin.site.register(models.VinculoEvidencia)
admin.site.register(models.PendenciaDocumental)
admin.site.register(models.RevisaoLaboratorio)
