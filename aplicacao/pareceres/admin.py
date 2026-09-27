from django.contrib import admin

from aplicacao.pareceres.models import AfirmacaoPreAnalise, FonteAfirmacaoPreAnalise, PreAnaliseTecnica, RevisaoPreAnalise, SecaoPreAnalise


class SecaoInline(admin.TabularInline):
    model = SecaoPreAnalise
    extra = 0


@admin.register(PreAnaliseTecnica)
class PreAnaliseAdmin(admin.ModelAdmin):
    list_display = ("codigo", "versao", "status", "prestacao_contas", "gerada_em")
    readonly_fields = ("hash_conteudo", "diagnostico_ia")
    inlines = [SecaoInline]


admin.site.register(AfirmacaoPreAnalise)
admin.site.register(FonteAfirmacaoPreAnalise)
admin.site.register(RevisaoPreAnalise)
