from pypdf import PdfReader
from pypdf.errors import PdfReadError

from aplicacao.documentos.escolhas import MetodoExtracao
from aplicacao.documentos.ocr import ServicoOCR
from aplicacao.documentos.qualidade import avaliar_qualidade


class ErroExtracao(Exception):
    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)


class ExtratorPDF:
    def __init__(self, ocr: ServicoOCR | None = None):
        self.ocr = ocr or ServicoOCR()

    def extrair(self, caminho) -> list[dict]:
        try:
            leitor = PdfReader(str(caminho))
        except PdfReadError as exc:
            raise ErroExtracao("O PDF está corrompido ou não pode ser lido.") from exc
        except Exception as exc:
            raise ErroExtracao("O PDF está corrompido ou não pode ser lido.") from exc
        if getattr(leitor, "is_encrypted", False):
            raise ErroExtracao("PDF protegido por senha não é suportado nesta onda.")
        if not leitor.pages:
            raise ErroExtracao("O PDF não contém páginas.")
        return [self._pagina(caminho, numero, pagina) for numero, pagina in enumerate(leitor.pages, start=1)]

    def _pagina(self, caminho, numero: int, pagina) -> dict:
        try:
            texto_nativo = pagina.extract_text() or ""
        except Exception:
            texto_nativo = ""
        qualidade, necessita_ocr = avaliar_qualidade(texto_nativo)
        texto_ocr = ""
        caixas: list[dict] = []
        ocr_executado = False
        erro_ocr = ""
        if necessita_ocr:
            try:
                texto_ocr, caixas = self.ocr.extrair_pagina(caminho, numero)
                ocr_executado = True
            except Exception as exc:
                erro_ocr = str(exc)[:300]
        texto_final, metodo = _combinar(texto_nativo, texto_ocr, necessita_ocr)
        if texto_final.strip() and metodo != MetodoExtracao.SEM_TEXTO:
            qualidade_final, _ = avaliar_qualidade(texto_final)
            if not necessita_ocr:
                qualidade_final = qualidade
        else:
            qualidade_final = qualidade
        return {
            "numero_pagina": numero,
            "texto_extraido": texto_final,
            "metodo_extracao": metodo,
            "qualidade_extracao": qualidade_final,
            "necessitou_ocr": necessita_ocr,
            "ocr_executado": ocr_executado,
            "quantidade_caracteres": len(texto_final),
            "dados_posicionais": {"caixas": caixas} if caixas else {},
            "erro_ocr": erro_ocr,
        }


def _combinar(texto_nativo: str, texto_ocr: str, necessitou_ocr: bool) -> tuple[str, str]:
    nativo = (texto_nativo or "").strip()
    ocr = (texto_ocr or "").strip()
    if not necessitou_ocr:
        return texto_nativo or "", MetodoExtracao.NATIVO
    if nativo and ocr:
        escolhido = texto_ocr if len(ocr) >= len(nativo) else texto_nativo
        return escolhido, MetodoExtracao.HIBRIDO
    if ocr:
        return texto_ocr, MetodoExtracao.OCR
    if nativo:
        return texto_nativo, MetodoExtracao.NATIVO
    return "", MetodoExtracao.SEM_TEXTO
