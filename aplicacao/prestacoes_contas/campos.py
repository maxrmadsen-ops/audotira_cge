from django.db import models


class DinheiroField(models.DecimalField):
    """Valor monetário. Nunca use float para dinheiro."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 16)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)
