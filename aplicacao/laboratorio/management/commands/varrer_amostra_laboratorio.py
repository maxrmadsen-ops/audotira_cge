"""Varredura local por OCR seletivo para localizar páginas da amostra de referência."""

from django.core.management.base import BaseCommand, CommandError

from aplicacao.documentos.armazenamento import ler_arquivo
from aplicacao.documentos.ocr import ServicoOCR
from aplicacao.laboratorio.models import LoteLaboratorio
from aplicacao.laboratorio.servico import processar_lote


class Command(BaseCommand):
    help = (
        "Percorre páginas físicas com OCR local em lotes, procurando termos da amostra. "
        "Não envia documento a provedor externo."
    )

    def add_arguments(self, parser):
        parser.add_argument("--lote-id", type=int, required=True)
        parser.add_argument("--inicio", type=int, default=1)
        parser.add_argument("--fim", type=int, default=0, help="0 = até a última página")
        parser.add_argument("--passo", type=int, default=1)
        parser.add_argument(
            "--termos",
            type=str,
            default="holerite,rescisão,rescisao,quitação,quitacao,fgts,dispensa,transferência,transferencia,líquido,liquido",
        )
        parser.add_argument("--reprocessar-encontradas", action="store_true")

    def handle(self, *args, **options):
        lote = LoteLaboratorio.objects.select_related("documento").filter(pk=options["lote_id"]).first()
        if lote is None:
            raise CommandError("Lote não encontrado.")
        fim = options["fim"] or lote.quantidade_paginas or 0
        if fim <= 0:
            raise CommandError("Lote sem quantidade de páginas. Processe o inventário antes.")
        termos = [t.strip().lower() for t in options["termos"].split(",") if t.strip()]
        caminho = ler_arquivo(lote.documento.nome_armazenado)
        ocr = ServicoOCR()
        encontradas: list[int] = []
        for numero in range(options["inicio"], fim + 1, max(1, options["passo"])):
            try:
                texto, _ = ocr.extrair_pagina(caminho, numero)
            except Exception as exc:
                self.stdout.write(f"PAGINA={numero} ERRO_OCR={str(exc)[:120]}")
                continue
            baixo = (texto or "").lower()
            hits = [termo for termo in termos if termo in baixo]
            chars = len((texto or "").strip())
            self.stdout.write(f"PAGINA={numero} CHARS={chars} HITS={','.join(hits) if hits else '-'}")
            if hits:
                encontradas.append(numero)
        self.stdout.write(f"ENCONTRADAS={','.join(str(n) for n in encontradas) if encontradas else 'nenhuma'}")
        if options["reprocessar_encontradas"] and encontradas:
            processar_lote(lote.pk, paginas_ocr=set(encontradas))
            self.stdout.write(f"REPROCESSADO_COM_OCR={len(encontradas)}")
