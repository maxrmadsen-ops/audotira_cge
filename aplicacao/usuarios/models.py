from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuário da solução, com perfil de acesso aplicado no backend."""

    class Perfil(models.TextChoices):
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
        AUDITOR = "AUDITOR", "Auditor"
        ANALISTA = "ANALISTA", "Analista"
        # Legado: permanece no enum para registros históricos. Não atribuível.
        CONSULTA = "CONSULTA", "Consulta (legado)"

    perfil = models.CharField(
        "perfil",
        max_length=20,
        choices=Perfil.choices,
        default=Perfil.ANALISTA,
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self) -> str:
        return f"{self.username} ({self.get_perfil_display()})"
