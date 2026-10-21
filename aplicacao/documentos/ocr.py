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

    def extrair_imagem(self, imagem) -> str:
        try:
            import pytesseract
            from PIL import ImageOps
        except ImportError as exc:
            raise RuntimeError("OCR indisponível: dependências não instaladas.") from exc
        idioma = settings.OCR_IDIOMA
        preparada = ImageOps.autocontrast(imagem.convert("L"))
        try:
            return pytesseract.image_to_string(preparada, lang=idioma, config="--psm 6") or ""
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError("OCR indisponível: Tesseract não encontrado.") from exc
        except Exception as exc:
            raise RuntimeError("Falha ao executar o OCR desta região.") from exc

    def extrair_imagem_com_caixas(self, imagem) -> tuple[str, list[dict]]:
        try:
            import pytesseract
            from PIL import ImageOps
        except ImportError as exc:
            raise RuntimeError("OCR indisponível: dependências não instaladas.") from exc
        idioma = settings.OCR_IDIOMA
        preparada = ImageOps.autocontrast(imagem.convert("L"))
        try:
            texto = pytesseract.image_to_string(preparada, lang=idioma, config="--psm 6") or ""
            dados = pytesseract.image_to_data(
                preparada,
                lang=idioma,
                config="--psm 6",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError("OCR indisponível: Tesseract não encontrado.") from exc
        except Exception as exc:
            raise RuntimeError("Falha ao executar o OCR desta região.") from exc
        largura, altura = preparada.size
        caixas = []
        for indice, palavra in enumerate(dados.get("text", [])):
            if not str(palavra).strip() or largura <= 0 or altura <= 0:
                continue
            caixas.append(
                {
                    "texto": str(palavra),
                    "x": int(dados["left"][indice]) / largura,
                    "y": int(dados["top"][indice]) / altura,
                    "largura": max(int(dados["width"][indice]) / largura, 0.001),
                    "altura": max(int(dados["height"][indice]) / altura, 0.001),
                }
            )
        return texto, caixas
