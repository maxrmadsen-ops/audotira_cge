from django.contrib import admin

from aplicacao.normas.models import AplicabilidadeNorma, DocumentoNormativo, Norma, RelacionamentoNorma, TrechoNormativo


class AplicabilidadeInline(admin.TabularInline):
    model = AplicabilidadeNorma
    extra = 0


class TrechoInline(admin.TabularInline):
    model = TrechoNormativo
    extra = 0
    fields = ("ordem", "artigo", "paragrafo", "inciso", "pagina_inicio", "hash_conteudo")
    readonly_fields = fields
    can_delete = False


@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ("numero", "ano", "tipo_norma", "versao", "situacao", "status_processamento", "inicio_vigencia", "fim_vigencia")
    search_fields = ("numero", "titulo", "hash_sha256")
    inlines = [AplicabilidadeInline, TrechoInline]


@admin.register(DocumentoNormativo)
class DocumentoNormativoAdmin(admin.ModelAdmin):
    list_display = ("norma", "natureza", "redacao", "versao", "situacao_conferencia", "data_obtencao")
    search_fields = ("fonte", "identificacao", "hash_sha256")
    readonly_fields = ("hash_sha256", "arquivo", "criado_em", "conferido_em")


@admin.register(RelacionamentoNorma)
class RelacionamentoNormaAdmin(admin.ModelAdmin):
    list_display = ("origem", "tipo", "destino")
