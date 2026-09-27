"""Completa o cenário sintético quando o catálogo de regras já existe."""

from datetime import date
from decimal import Decimal

from aplicacao.achados.gerador import gerar_achados
from aplicacao.achados.models import Achado
from aplicacao.normas.escolhas import TipoNorma
from aplicacao.normas.models import Norma, TrechoNormativo
from aplicacao.regras.escolhas import StatusTecnico
from aplicacao.regras.models import CalculoExecucaoRegra, ExecucaoAnalise, ExecucaoRegra, ReferenciaExecucao, RegraAnalise


def garantir_demonstracao_achados(prestacao):
    if not RegraAnalise.objects.filter(ativa=True, codigo="FIN-003").exists():
        return None
    if Achado.objects.filter(prestacao_contas=prestacao, demonstracao=True).exists():
        return Achado.objects.filter(prestacao_contas=prestacao, demonstracao=True).first()
    despesa = prestacao.despesas.filter(descricao="DEMO-REGRAS divergência de valor").first()
    if despesa is None:
        return None
    analise = ExecucaoAnalise.objects.create(
        prestacao_contas=prestacao,
        versao_catalogo="demonstracao",
        sintese="NÃO CONCLUSIVO",
    )
    financeira = RegraAnalise.objects.get(codigo="FIN-003", ativa=True)
    relacionada = RegraAnalise.objects.filter(ativa=True, codigo="FIN-005").first() or financeira
    trecho = _trecho_sintetico()
    primeira = _executar(
        analise,
        financeira,
        "DIVERGÊNCIA",
        StatusTecnico.DIVERGENCIA,
        despesa,
        papel="valor_documentado",
        calculo=True,
        trecho_normativo=trecho,
    )
    pagamento = prestacao.pagamentos.order_by("id").first()
    if pagamento is not None:
        ReferenciaExecucao.objects.create(
            execucao=primeira,
            tipo_fonte="pagamento",
            identificador=str(pagamento.pk),
            valor_utilizado="950.00",
            papel_na_regra="valor_pago",
        )
    _executar(analise, relacionada, "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, despesa, papel="contradiz", calculo=True)
    vedacao = RegraAnalise.objects.filter(ativa=True, codigo="VED-001").first()
    if vedacao is not None:
        _executar(analise, vedacao, "DIVERGÊNCIA", StatusTecnico.DIVERGENCIA, despesa, papel="vedacao", calculo=False)
    devolucao = RegraAnalise.objects.filter(ativa=True, codigo="DEV-001").first()
    if devolucao is not None:
        _executar(analise, devolucao, "DEVOLVIDO", StatusTecnico.SUCESSO, despesa, papel="devolucao", calculo=False)
        _executar(analise, devolucao, "POSSÍVEL SALDO NÃO DEVOLVIDO", StatusTecnico.ATENCAO, None, calculo=False)
        _executar(analise, devolucao, "NÃO VERIFICÁVEL", StatusTecnico.INCONCLUSIVO, None, calculo=False)
    gerar_achados(analise.pk)
    return Achado.objects.filter(analise=analise, materialidade_financeira__isnull=False).first()


def _executar(analise, regra, resultado, status, despesa, papel="fato", calculo=False, trecho_normativo=None):
    execucao = ExecucaoRegra.objects.create(
        analise=analise,
        regra=regra,
        resultado_funcional=resultado,
        status_tecnico=status,
        snapshot={"codigo": regra.codigo, "versao": regra.versao},
    )
    if despesa is not None:
        ReferenciaExecucao.objects.create(
            execucao=execucao,
            tipo_fonte="despesa",
            identificador=str(despesa.pk),
            valor_utilizado="1000.00",
            papel_na_regra=papel,
            trecho_normativo=trecho_normativo,
        )
    if calculo:
        CalculoExecucaoRegra.objects.create(
            execucao=execucao,
            operacao="diferenca",
            operandos={"valor_documentado": "1000.00", "valor_pago": "950.00"},
            resultado=Decimal("50.00"),
            unidade="BRL",
        )
    return execucao


def _trecho_sintetico():
    norma, _criada = Norma.objects.get_or_create(
        numero="DEMO-ACH",
        ano=2024,
        versao=1,
        defaults={
            "tipo_norma": TipoNorma.DECRETO,
            "titulo": "Norma sintética de demonstração",
            "inicio_vigencia": date(2020, 1, 1),
            "ementa": "Texto sintético para a demonstração. Não é norma real.",
        },
    )
    trecho, _criado = TrechoNormativo.objects.get_or_create(
        norma=norma,
        ordem=1,
        defaults={
            "texto": "Dispositivo sintético de demonstração.",
            "hash_conteudo": "d" * 64,
            "artigo": "1",
        },
    )
    return trecho
