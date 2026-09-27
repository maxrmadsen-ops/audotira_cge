from django.apps import AppConfig


class PareceresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao.pareceres"
    verbose_name = "Pré-análise técnica"

    def ready(self) -> None:
        from aplicacao.pareceres import tarefas  # noqa: F401
