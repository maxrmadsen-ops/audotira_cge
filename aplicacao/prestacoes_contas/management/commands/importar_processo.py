import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from aplicacao.prestacoes_contas.migracao_seletiva import (
    POLITICA_DESVINCULAR,
    POLITICA_EXIGIR,
    ConflitoMigracao,
    importar_processo,
)


class Command(BaseCommand):
    help = "Importa um processo exportado. Sem --aplicar, apenas confere conflitos."

    def add_arguments(self, parser):
        parser.add_argument("origem")
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--politica-catalogo", choices=[POLITICA_EXIGIR, POLITICA_DESVINCULAR], default=POLITICA_EXIGIR)

    def handle(self, *args, **options):
        try:
            resultado = importar_processo(
                Path(options["origem"]),
                aplicar=options["aplicar"],
                politica_catalogo=options["politica_catalogo"],
            )
        except ConflitoMigracao as exc:
            raise CommandError(json.dumps({"mensagem": str(exc), "conflitos": exc.conflitos}, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(resultado, ensure_ascii=False))
