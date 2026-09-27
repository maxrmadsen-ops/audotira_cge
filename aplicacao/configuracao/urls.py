from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "CGE — Administração técnica"
admin.site.site_title = "CGE"
admin.site.index_title = "Fundação da solução"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("aplicacao.pareceres.urls")),
    path("", include("aplicacao.achados.urls")),
    path("", include("aplicacao.inteligencia_artificial.urls")),
    path("", include("aplicacao.regras.urls")),
    path("", include("aplicacao.normas.urls")),
    path("", include("aplicacao.documentos.urls")),
    path("", include("aplicacao.prestacoes_contas.urls")),
    path("", include("aplicacao.painel.urls")),
    path("auditoria/", include("aplicacao.auditoria.urls")),
]
