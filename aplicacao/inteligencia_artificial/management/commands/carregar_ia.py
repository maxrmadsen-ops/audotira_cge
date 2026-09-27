from django.core.management.base import BaseCommand

from aplicacao.inteligencia_artificial.sementes import garantir_catalogo_ia


class Command(BaseCommand):
    help = "Cria modelos, prompts e limite iniciais da IA, sem preço comercial e sem chamada externa."

    def handle(self, *args, **options):
        garantir_catalogo_ia()
        self.stdout.write("Catálogo de IA sincronizado. Nenhuma chamada externa foi feita.")
