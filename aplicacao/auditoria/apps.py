from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao.auditoria"
    verbose_name = "Auditoria"

    def ready(self) -> None:
        from aplicacao.auditoria import sinais  # noqa: F401
