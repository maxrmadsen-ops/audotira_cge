from django.contrib import admin

from aplicacao.inteligencia_artificial.models import (
    ConfiguracaoRoteamento,
    EventoOperacionalProvedor,
    LimiteConsumoInteligenciaArtificial,
    ModeloInteligenciaArtificial,
    PrecoModeloInteligenciaArtificial,
    PromptInteligenciaArtificial,
    UsoInteligenciaArtificial,
    VersaoPromptInteligenciaArtificial,
)


@admin.register(ModeloInteligenciaArtificial)
class ModeloAdmin(admin.ModelAdmin):
    list_display = ("nome_exibicao", "provedor", "identificador_modelo", "ativo", "modelo_padrao", "finalidade")
    list_filter = ("provedor", "ativo", "finalidade")


@admin.register(PrecoModeloInteligenciaArtificial)
class PrecoAdmin(admin.ModelAdmin):
    list_display = ("modelo", "vigencia_inicio", "vigencia_fim", "moeda", "preco_entrada", "preco_saida")


class VersaoPromptInline(admin.TabularInline):
    model = VersaoPromptInteligenciaArtificial
    extra = 0
    fields = ("versao", "ativo", "utilizada", "criado_em")
    readonly_fields = ("utilizada", "criado_em")


@admin.register(PromptInteligenciaArtificial)
class PromptAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "agente")
    inlines = [VersaoPromptInline]


@admin.register(UsoInteligenciaArtificial)
class UsoAdmin(admin.ModelAdmin):
    list_display = ("iniciada_em", "provedor", "identificador_modelo", "agente", "status", "tokens_total", "duracao_ms", "fallback_utilizado", "laboratorio")
    readonly_fields = [campo.name for campo in UsoInteligenciaArtificial._meta.fields]


@admin.register(LimiteConsumoInteligenciaArtificial)
class LimiteAdmin(admin.ModelAdmin):
    list_display = ("escopo", "provedor", "max_caracteres_contexto", "max_tentativas", "ativo")


@admin.register(ConfiguracaoRoteamento)
class RoteamentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "provedor_principal", "modelo_principal", "provedor_fallback", "modelo_fallback", "ativo")


@admin.register(EventoOperacionalProvedor)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("ocorrido_em", "provedor", "erro_normalizado")
    readonly_fields = ("ocorrido_em", "provedor", "erro_normalizado")
