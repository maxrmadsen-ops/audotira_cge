from django.contrib import admin

from aplicacao.avaliacao.models import (
    AvaliacaoInteligenciaArtificial,
    ComparacaoRegra,
    CorrespondenciaAchado,
    GroundTruthAchado,
    GroundTruthPrestacao,
    GroundTruthRegra,
    RevisaoCorrespondencia,
    SnapshotAvaliacao,
)


class RegraInline(admin.TabularInline):
    model = GroundTruthRegra
    extra = 0


@admin.register(GroundTruthPrestacao)
class GroundTruthAdmin(admin.ModelAdmin):
    list_display = ("codigo", "versao", "modo", "status", "prestacao_contas", "dados_demonstracao")
    readonly_fields = ("hash_conteudo",)
    inlines = [RegraInline]


admin.site.register(GroundTruthAchado)
admin.site.register(SnapshotAvaliacao)
admin.site.register(AvaliacaoInteligenciaArtificial)
admin.site.register(ComparacaoRegra)
admin.site.register(CorrespondenciaAchado)
admin.site.register(RevisaoCorrespondencia)
