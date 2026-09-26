#!/usr/bin/env python
"""Ponto de entrada do Django. A aplicação deve ser executada no container."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aplicacao.configuracao.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Execute a aplicação pelo container."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
