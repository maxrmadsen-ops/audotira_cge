from django.apps import AppConfig


class AchadosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao.achados"
    verbose_name = "Achados"

    def ready(self) -> None:
        from aplicacao.achados import tarefas  # noqa: F401
