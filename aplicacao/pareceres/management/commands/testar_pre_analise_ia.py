from django.core.management.base import BaseCommand, CommandError

from aplicacao.pareceres.gerador import gerar_pre_analise
from aplicacao.prestacoes_contas.models import PrestacaoContas


class Command(BaseCommand):
    help = "Gera pré-análise somente sobre prestação sintética. Não chama provedor real e não entra na suíte."

    def add_arguments(self, parser):
        parser.add_argument("--habilitar", action="store_true")
        parser.add_argument("--processo", default="DEMO-2024-001")

    def handle(self, *args, **opcoes):
        if not opcoes["habilitar"]:
            raise CommandError("Informe --habilitar. O comando não roda sozinho e não usa Insumos Piloto nem Ground Truth.")
        prestacao = PrestacaoContas.objects.filter(numero_processo=opcoes["processo"], demonstracao=True).first()
        if prestacao is None:
            raise CommandError("Prestação sintética não encontrada. Nenhum dado real foi consultado.")
        analise = prestacao.execucoes_analise.order_by("-id").first()
        if analise is None:
            raise CommandError("A prestação sintética não tem execução de análise.")
        pre = gerar_pre_analise(analise, demonstracao=True)
        self.stdout.write(f"{pre.codigo} v{pre.versao} {pre.status}")
