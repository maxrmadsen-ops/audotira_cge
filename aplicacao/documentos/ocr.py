from django.conf import settings


class ServicoOCR:
    """OCR local com Tesseract. Uma falha de página não encerra o documento."""

    def extrair_pagina(self, caminho, numero_pagina: int) -> tuple[str, list[dict]]:
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError as exc:
            raise RuntimeError("OCR indisponível: dependências não instaladas.") from exc
        try:
            imagens = convert_from_path(
                str(caminho),
                dpi=200,
                first_page=numero_pagina,
                last_page=numero_pagina,
            )
        except Exception as exc:
            raise RuntimeError("Não foi possível rasterizar a página para OCR.") from exc
        if not imagens:
            raise RuntimeError("A página não gerou imagem para OCR.")
        imagem = imagens[0]
        idioma = settings.OCR_IDIOMA
        try:
            texto = pytesseract.image_to_string(imagem, lang=idioma) or ""
            dados = pytesseract.image_to_data(imagem, lang=idioma, output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError("OCR indisponível: Tesseract não encontrado.") from exc
        except Exception as exc:
            raise RuntimeError("Falha ao executar o OCR desta página.") from exc
        caixas = []
        textos = dados.get("text", [])
        for indice, palavra in enumerate(textos):
            if not str(palavra).strip():
                continue
            caixas.append(
                {
                    "texto": str(palavra),
                    "x": int(dados["left"][indice]),
                    "y": int(dados["top"][indice]),
                    "largura": int(dados["width"][indice]),
                    "altura": int(dados["height"][indice]),
                }
            )
            if len(caixas) >= 200:
                break
        return texto, caixas
