from django.contrib import admin

from aplicacao.auditoria.models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("data_hora", "evento", "usuario", "endereco_ip", "caminho")
    list_filter = ("evento",)
    search_fields = ("descricao", "caminho", "usuario__username")
    readonly_fields = (
        "data_hora",
        "usuario",
        "evento",
        "descricao",
        "endereco_ip",
        "caminho",
        "detalhes",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
