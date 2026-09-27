from django.apps import AppConfig


class AvaliacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicacao.avaliacao"
    verbose_name = "Ground Truth e avaliação"

    def ready(self) -> None:
        from aplicacao.avaliacao import tarefas  # noqa: F401
