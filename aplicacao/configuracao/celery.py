"""Aplicação Celery da fundação. Tarefas de domínio entram nas ondas seguintes."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aplicacao.configuracao.settings")

app = Celery("cge")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
