"""Healthcheck do worker Celery. Não expõe segredos."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from aplicacao.configuracao.celery import app  # noqa: E402


def main() -> int:
    try:
        respostas = app.control.ping(timeout=8.0) or []
    except Exception:
        return 1
    return 0 if respostas else 1


if __name__ == "__main__":
    sys.exit(main())
