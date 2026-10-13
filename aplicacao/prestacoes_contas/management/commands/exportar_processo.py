from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from aplicacao.prestacoes_contas.migracao_seletiva import ConflitoMigracao, exportar_processo


class Command(BaseCommand):
    help = "Exporta um processo e seus documentos, sem credenciais e sem alterar o banco."

    def add_arguments(self, parser):
        parser.add_argument("numero_processo")
        parser.add_argument("destino")

    def handle(self, *args, **options):
        try:
            contagens = exportar_processo(options["numero_processo"], Path(options["destino"]))
        except ConflitoMigracao as exc:
            raise CommandError(str(exc)) from exc
        for nome, quantidade in sorted(contagens.items()):
            self.stdout.write(f"{nome}: {quantidade}")
