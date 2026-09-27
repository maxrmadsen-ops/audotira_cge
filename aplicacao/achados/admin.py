from django.contrib import admin

from aplicacao.achados.models import Achado, Evidencia, FundamentacaoAchado, RevisaoAchado, Sinalizacao


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo", "prestacao_contas", "metodo_obtencao", "confiabilidade_origem", "criada_em")
    search_fields = ("codigo", "trecho")


@admin.register(Achado)
class AchadoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "status", "natureza", "tipo_constatacao", "criticidade", "prioridade", "materialidade_financeira")
    search_fields = ("codigo", "titulo")


admin.site.register(Sinalizacao)
admin.site.register(FundamentacaoAchado)
admin.site.register(RevisaoAchado)
