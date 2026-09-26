import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def pdf_com_texto(linhas: list[str], paginas: int = 1) -> bytes:
    buffer = io.BytesIO()
    documento = canvas.Canvas(buffer, pagesize=A4)
    for indice in range(paginas):
        altura = 800
        for linha in linhas:
            documento.drawString(72, altura, linha)
            altura -= 18
        if indice == paginas - 1 and paginas > 1 and not linhas:
            pass
        documento.showPage()
    documento.save()
    return buffer.getvalue()


def pdf_textual_e_pagina_vazia(linhas: list[str]) -> bytes:
    buffer = io.BytesIO()
    documento = canvas.Canvas(buffer, pagesize=A4)
    altura = 800
    for linha in linhas:
        documento.drawString(72, altura, linha)
        altura -= 18
    documento.showPage()
    documento.showPage()
    documento.save()
    return buffer.getvalue()


def pdf_somente_imagem(texto: str) -> bytes:
    imagem = Image.new("RGB", (1400, 360), "white")
    desenho = ImageDraw.Draw(imagem)
    fonte = ImageFont.truetype(_fonte(), 54)
    desenho.text((40, 140), texto, fill="black", font=fonte)
    buffer_imagem = io.BytesIO()
    imagem.save(buffer_imagem, format="PNG")
    buffer_imagem.seek(0)
    buffer = io.BytesIO()
    documento = canvas.Canvas(buffer, pagesize=A4)
    documento.drawImage(ImageReader(buffer_imagem), 40, 520, width=520, height=134)
    documento.showPage()
    documento.save()
    return buffer.getvalue()


def _fonte() -> str:
    candidatos = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for caminho in candidatos:
        if Path(caminho).is_file():
            return caminho
    raise FileNotFoundError("Fonte do sistema não encontrada para o PDF sintético.")
