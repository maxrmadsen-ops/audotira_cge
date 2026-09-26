from django.contrib import admin

from aplicacao.usuarios.models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("username", "first_name", "perfil", "is_active", "is_staff", "last_login")
    list_filter = ("perfil", "is_active", "is_staff")
    search_fields = ("username", "first_name", "email")
    ordering = ("username",)
