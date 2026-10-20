from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from aplicacao.laboratorio.servico import ErroLaboratorio, importar_pdf, processar_lote
from aplicacao.prestacoes_contas.models import PrestacaoContas


class Command(BaseCommand):
    help = "Importa PDF imutável no laboratório documental e processa o inventário local."

    def add_arguments(self, parser):
        parser.add_argument("--prestacao-id", type=int, required=True)
        parser.add_argument("--arquivo", type=str, required=True)
        parser.add_argument("--processo-parcial", type=str, required=True)
        parser.add_argument("--instrumento", type=str, default="")
        parser.add_argument("--origem", type=str, default="")
        parser.add_argument("--usuario", type=str, default="")
        parser.add_argument("--somente-importar", action="store_true")
        parser.add_argument("--com-ocr", action="store_true", help="OCR em todas as páginas (lento).")
        parser.add_argument(
            "--ocr-paginas",
            type=str,
            default="",
            help="Lista de páginas físicas para OCR seletivo, separadas por vírgula.",
        )

    def handle(self, *args, **options):
        prestacao = PrestacaoContas.objects.filter(pk=options["prestacao_id"]).first()
        if prestacao is None:
            raise CommandError("Prestação não encontrada.")
        caminho = Path(options["arquivo"])
        if not caminho.is_file():
            raise CommandError(f"Arquivo inexistente: {caminho}")
        usuario = None
        if options["usuario"]:
            usuario = get_user_model().objects.filter(username=options["usuario"]).first()
        try:
            lote = importar_pdf(
                prestacao=prestacao,
                caminho=caminho,
                numero_processo_parcial=options["processo_parcial"],
                numero_instrumento=options["instrumento"],
                origem=options["origem"] or str(caminho),
                usuario=usuario,
            )
        except ErroLaboratorio as exc:
            raise CommandError(exc.mensagem) from exc
        self.stdout.write(
            f"LOTE={lote.pk} HASH={lote.hash_sha256} BYTES={lote.tamanho_bytes} DOC={lote.documento_id}"
        )
        if options["somente_importar"]:
            return
        paginas_ocr = set()
        if options["ocr_paginas"]:
            paginas_ocr = {int(item.strip()) for item in options["ocr_paginas"].split(",") if item.strip()}
        lote = processar_lote(
            lote.pk,
            usuario=usuario,
            com_ocr=bool(options["com_ocr"]),
            paginas_ocr=paginas_ocr or None,
        )
        self.stdout.write(
            f"PROCESSADO PAGINAS={lote.quantidade_paginas} "
            f"MS={lote.duracao_processamento_ms} TECNICA={lote.tecnica_predominante}"
        )
