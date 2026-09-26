from dataclasses import dataclass
from datetime import date

from aplicacao.prestacoes_contas.escolhas import TipoPrestacaoParcial


@dataclass(frozen=True)
class Marco:
    data: date | None
    titulo: str
    tipo: str
    detalhe: str


def montar_linha_do_tempo(prestacao) -> list[Marco]:
    marcos: list[Marco] = []
    for instrumento in prestacao.instrumentos.all():
        marcos.append(
            Marco(
                data=instrumento.data_assinatura or instrumento.vigencia_inicio,
                titulo=f"Instrumento {instrumento.numero}".strip(),
                tipo="Instrumento",
                detalhe=instrumento.get_tipo_display(),
            )
        )
    for plano in prestacao.planos.all():
        marcos.append(
            Marco(
                data=plano.vigencia_inicio,
                titulo=plano.titulo,
                tipo="Plano de trabalho",
                detalhe=f"Versão {plano.versao}",
            )
        )
    for parcial in prestacao.parciais.all():
        titulo = "Prestação final" if parcial.tipo == TipoPrestacaoParcial.FINAL else f"Prestação parcial {parcial.numero_ordem:02d}"
        marcos.append(
            Marco(
                data=parcial.periodo_inicio,
                titulo=titulo,
                tipo="Prestação",
                detalhe=parcial.descricao,
            )
        )
    for pagamento in prestacao.pagamentos.all():
        marcos.append(
            Marco(
                data=pagamento.data,
                titulo="Pagamento",
                tipo="Pagamento",
                detalhe=pagamento.identificador or pagamento.get_meio_display(),
            )
        )
    for devolucao in prestacao.devolucoes.all():
        marcos.append(
            Marco(
                data=devolucao.data,
                titulo="Devolução",
                tipo="Devolução",
                detalhe=devolucao.motivo,
            )
        )
    com_data = sorted((marco for marco in marcos if marco.data), key=lambda marco: marco.data)
    sem_data = [marco for marco in marcos if not marco.data]
    return com_data + sem_data
