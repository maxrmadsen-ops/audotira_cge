from django.core.management.base import BaseCommand

from aplicacao.regras.catalogo import sincronizar_catalogo


class Command(BaseCommand):
    help = "Carrega o catálogo das regras CGE a partir da semente versionada. A planilha original não é necessária."

    def handle(self, *args, **options):
        resumo = sincronizar_catalogo()
        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo sincronizado. Criadas ou versionadas: {resumo['criadas']}. Mantidas: {resumo['mantidas']}. Total: {resumo['total']}."
            )
        )
