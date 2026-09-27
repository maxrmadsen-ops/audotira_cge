from django.contrib import admin

from aplicacao.regras.models import ExecucaoAnalise, ExecucaoRegra, RegraAnalise, RegraDependencia


class DependenciaInline(admin.TabularInline):
    model = RegraDependencia
    extra = 0


@admin.register(RegraAnalise)
class RegraAnaliseAdmin(admin.ModelAdmin):
    list_display = ("codigo", "versao", "categoria", "tipo_execucao", "capacidade", "ativa")
    list_filter = ("categoria", "tipo_execucao", "capacidade", "ativa")
    search_fields = ("codigo", "titulo")
    inlines = [DependenciaInline]


@admin.register(ExecucaoAnalise)
class ExecucaoAnaliseAdmin(admin.ModelAdmin):
    list_display = ("id", "prestacao_contas", "modo_execucao", "status", "sintese", "criado_em")


@admin.register(ExecucaoRegra)
class ExecucaoRegraAdmin(admin.ModelAdmin):
    list_display = ("regra", "resultado_funcional", "status_tecnico", "encaminhamento")
