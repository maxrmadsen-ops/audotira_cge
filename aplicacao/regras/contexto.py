import unicodedata
from datetime import date

from aplicacao.documentos.escolhas import TipoDocumento
from aplicacao.normas.resolvedor import ResolvedorNormativo
from aplicacao.prestacoes_contas.escolhas import TipoMovimentacao
from aplicacao.regras.escolhas import FONTE_EXCLUIDA_TESTE_CEGO
from aplicacao.regras.resultados import dinheiro, referencia, somar

MARCADORES_ANALISE_PREVIA = (
    "analise tecnica",
    "parecer tecnico",
    "informacoes da analise",
    "informacoes decorrentes da analise",
)


def normalizar(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(caractere for caractere in decomposicao if not unicodedata.combining(caractere))
    return sem_acento.casefold()


def digitos(texto: str) -> str:
    return "".join(caractere for caractere in (texto or "") if caractere.isdigit())


def contem_analise_tecnica_previa(documento) -> bool:
    if (documento.subtipo_documento or "") == FONTE_EXCLUIDA_TESTE_CEGO:
        return True
    if documento.tipo_documento not in {TipoDocumento.PRESTACAO_PARCIAL, TipoDocumento.PRESTACAO_FINAL}:
        return False
    texto = normalizar(f"{documento.nome_original} {documento.subtipo_documento}")
    return any(marcador in texto for marcador in MARCADORES_ANALISE_PREVIA)


class ContextoExecucao:
    def __init__(self, prestacao, documentos, modo_teste_cego: bool, excluidos: list[dict]):
        self.prestacao = prestacao
        self.documentos = documentos
        self.modo_teste_cego = modo_teste_cego
        self.excluidos = excluidos
        self.resultados: dict[str, object] = {}
        self._resolucao = None
        self._despesas = None

    @classmethod
    def montar(cls, prestacao, modo_teste_cego: bool):
        documentos = list(prestacao.documentos.ativos().prefetch_related("paginas", "dados_extraidos"))
        excluidos = []
        permitidos = []
        for documento in documentos:
            if modo_teste_cego and contem_analise_tecnica_previa(documento):
                excluidos.append(
                    {
                        "documento_id": documento.id,
                        "nome": documento.nome_original,
                        "motivo": FONTE_EXCLUIDA_TESTE_CEGO,
                    }
                )
            else:
                permitidos.append(documento)
        return cls(prestacao, permitidos, modo_teste_cego, excluidos)

    def instrumento(self):
        return self.prestacao.instrumento_principal

    def despesas(self):
        if self._despesas is None:
            self._despesas = list(
                self.prestacao.despesas.select_related("fornecedor__entidade", "item_plano").prefetch_related(
                    "documentos_fiscais__emitente__entidade",
                    "pagamentos__movimentacoes",
                )
            )
        return self._despesas

    def pagamentos(self):
        return list(self.prestacao.pagamentos.prefetch_related("movimentacoes", "despesas", "documentos_fiscais"))

    def movimentacoes(self):
        return list(self.prestacao.movimentacoes.prefetch_related("pagamentos"))

    def itens_plano(self):
        return list(self.prestacao.planos.prefetch_related("itens__despesas", "metas"))

    def data_referencia(self) -> date | None:
        instrumento = self.instrumento()
        if instrumento and instrumento.data_assinatura:
            return instrumento.data_assinatura
        return self.prestacao.data_inicio

    def resolucao_normativa(self):
        if self._resolucao is None:
            data = self.data_referencia()
            if data is None:
                self._resolucao = None
            else:
                self._resolucao = ResolvedorNormativo().resolver(
                    data_referencia=data,
                    prestacao_contas=self.prestacao,
                )
        return self._resolucao

    def referencias_normativas(self) -> list[dict]:
        resolucao = self.resolucao_normativa()
        if resolucao is None:
            return []
        return [
            referencia(
                tipo_fonte="norma",
                identificador=item.norma.id,
                campo="vigencia",
                valor_utilizado=item.motivo,
                papel_na_regra="norma_elegivel",
            )
            for item in resolucao.elegiveis
        ]

    def documento_corresponde(self, documento, tipos=None, nomes=None) -> bool:
        if tipos and documento.tipo_documento in tipos:
            return True
        if nomes:
            texto = normalizar(f"{documento.nome_original} {documento.subtipo_documento}")
            return any(normalizar(nome) in texto for nome in nomes)
        return False

    def documentos_correspondentes(self, tipos=None, nomes=None):
        return [documento for documento in self.documentos if self.documento_corresponde(documento, tipos, nomes)]

    def referencias_documentos(self, documentos, papel: str) -> list[dict]:
        refs = []
        for documento in documentos:
            refs.append(
                referencia(
                    tipo_fonte="documento",
                    identificador=documento.id,
                    documento_id=documento.id,
                    campo="nome_original",
                    valor_utilizado=documento.nome_original,
                    papel_na_regra=papel,
                )
            )
        return refs

    def pares_despesa(self):
        pares = []
        for despesa in self.despesas():
            fiscais = list(despesa.documentos_fiscais.all())
            pagamentos = list(despesa.pagamentos.all())
            valor_documentado = somar(fiscal.valor for fiscal in fiscais)
            valor_pago = somar(pagamento.valor for pagamento in pagamentos)
            movimentos = []
            for pagamento in pagamentos:
                movimentos.extend(list(pagamento.movimentacoes.all()))
            valor_extrato = somar(movimento.valor for movimento in movimentos)
            pares.append(
                {
                    "despesa": despesa,
                    "fiscais": fiscais,
                    "pagamentos": pagamentos,
                    "movimentos": movimentos,
                    "valor_documentado": valor_documentado,
                    "valor_pago": valor_pago,
                    "valor_extrato": valor_extrato,
                }
            )
        return pares

    def saldo_estruturado(self):
        movimentos = self.movimentacoes()
        if not movimentos:
            return None
        creditos = somar(item.valor for item in movimentos if item.tipo == TipoMovimentacao.CREDITO)
        debitos = somar(item.valor for item in movimentos if item.tipo == TipoMovimentacao.DEBITO)
        return (creditos or dinheiro(0)) - (debitos or dinheiro(0))
