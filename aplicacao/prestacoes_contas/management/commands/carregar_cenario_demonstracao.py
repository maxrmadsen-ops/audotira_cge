from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from aplicacao.entidades.models import Entidade, Fornecedor, Funcionario, Pessoa
from aplicacao.prestacoes_contas.escolhas import (
    FasePrestacao,
    MeioPagamento,
    NaturezaItem,
    SituacaoPrestacao,
    TipoDocumentoFiscal,
    TipoInstrumento,
    TipoMovimentacao,
    TipoPrestacaoParcial,
)
from aplicacao.prestacoes_contas.models import (
    Contrapartida,
    Despesa,
    Devolucao,
    DocumentoFiscal,
    Instrumento,
    ItemPlanoTrabalho,
    Meta,
    MovimentacaoBancaria,
    Pagamento,
    PlanoTrabalho,
    PrestacaoContas,
    PrestacaoParcial,
)

PROCESSO = "DEMO-2024-001"


class Command(BaseCommand):
    help = "Carrega um cenário sintético de prestação de contas, marcado como demonstração."

    @transaction.atomic
    def handle(self, *args, **options):
        if PrestacaoContas.objects.filter(numero_processo=PROCESSO).exists():
            self.stdout.write("Cenário de demonstração já existe.")
            return

        concedente = Entidade.objects.create(
            nome="Secretaria Municipal de Demonstração",
            tipo=Entidade.Tipo.CONCEDENTE,
            municipio="Cidade Exemplo",
            uf="SC",
            demonstracao=True,
        )
        beneficiario = Entidade.objects.create(
            nome="Associação Comunitária Exemplo",
            tipo=Entidade.Tipo.BENEFICIARIO,
            municipio="Cidade Exemplo",
            uf="SC",
            demonstracao=True,
        )
        entidade_fornecedor = Entidade.objects.create(
            nome="Papelaria Exemplo Ltda",
            tipo=Entidade.Tipo.FORNECEDOR,
            demonstracao=True,
        )
        fornecedor = Fornecedor.objects.create(entidade=entidade_fornecedor, ramo="Material de escritório", demonstracao=True)
        pessoa = Pessoa.objects.create(nome="Maria Demonstração", demonstracao=True)
        Funcionario.objects.create(
            pessoa=pessoa,
            entidade=beneficiario,
            cargo="Oficineira",
            remuneracao_base=Decimal("1800.00"),
            situacao=Funcionario.Situacao.ATIVO,
            demonstracao=True,
        )

        prestacao = PrestacaoContas.objects.create(
            numero_processo=PROCESSO,
            concedente=concedente,
            beneficiario=beneficiario,
            objeto="Oficinas comunitárias fictícias para demonstração do sistema.",
            valor_total=Decimal("10000.00"),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 31),
            situacao=SituacaoPrestacao.EM_ELABORACAO,
            fase=FasePrestacao.EXECUCAO,
            demonstracao=True,
        )
        instrumento = Instrumento.objects.create(
            prestacao=prestacao,
            numero="TF-DEMO-014",
            tipo=TipoInstrumento.TERMO_FOMENTO,
            data_assinatura=date(2024, 1, 10),
            vigencia_inicio=date(2024, 1, 1),
            vigencia_fim=date(2024, 12, 31),
            valor=Decimal("10000.00"),
            principal=True,
            demonstracao=True,
        )
        plano = PlanoTrabalho.objects.create(
            prestacao=prestacao,
            instrumento=instrumento,
            titulo="Plano de oficinas de demonstração",
            versao=1,
            vigencia_inicio=date(2024, 1, 1),
            vigencia_fim=date(2024, 12, 31),
            demonstracao=True,
        )
        item_pessoal = ItemPlanoTrabalho.objects.create(
            plano=plano,
            categoria="Pessoal",
            descricao="Remuneração de oficineira de demonstração",
            quantidade=Decimal("12.000"),
            unidade="mês",
            valor_previsto=Decimal("5000.00"),
            natureza=NaturezaItem.PESSOAL,
            ordem=1,
            demonstracao=True,
        )
        item_material = ItemPlanoTrabalho.objects.create(
            plano=plano,
            categoria="Material",
            descricao="Material de papelaria de demonstração",
            quantidade=Decimal("1.000"),
            unidade="lote",
            valor_previsto=Decimal("800.00"),
            natureza=NaturezaItem.MATERIAL,
            ordem=2,
            demonstracao=True,
        )
        Meta.objects.create(
            plano=plano,
            codigo="M1",
            descricao="Realizar quatro oficinas fictícias",
            indicador="oficinas realizadas",
            quantidade_prevista=Decimal("4.000"),
            unidade="oficina",
            demonstracao=True,
        )
        parcial = PrestacaoParcial.objects.create(
            prestacao=prestacao,
            tipo=TipoPrestacaoParcial.PARCIAL,
            numero_ordem=1,
            periodo_inicio=date(2024, 1, 1),
            periodo_fim=date(2024, 6, 30),
            descricao="Primeiro semestre de demonstração",
            demonstracao=True,
        )
        PrestacaoParcial.objects.create(
            prestacao=prestacao,
            tipo=TipoPrestacaoParcial.FINAL,
            numero_ordem=2,
            periodo_inicio=date(2024, 7, 1),
            periodo_fim=date(2024, 12, 31),
            descricao="Prestação final de demonstração",
            demonstracao=True,
        )
        despesa = Despesa.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            item_plano=item_material,
            fornecedor=fornecedor,
            descricao="Compra fictícia de material",
            valor=Decimal("800.00"),
            data=date(2024, 3, 15),
            natureza=NaturezaItem.MATERIAL,
            demonstracao=True,
        )
        documento = DocumentoFiscal.objects.create(
            prestacao=prestacao,
            emitente=fornecedor,
            tipo=TipoDocumentoFiscal.NOTA_FISCAL,
            numero="1001",
            data_emissao=date(2024, 3, 15),
            valor=Decimal("800.00"),
            demonstracao=True,
        )
        documento.despesas.add(despesa)
        pagamento = Pagamento.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            data=date(2024, 3, 20),
            valor=Decimal("800.00"),
            meio=MeioPagamento.PIX,
            identificador="PIX-DEMO-1001",
            demonstracao=True,
        )
        pagamento.despesas.add(despesa)
        pagamento.documentos_fiscais.add(documento)
        movimento = MovimentacaoBancaria.objects.create(
            prestacao=prestacao,
            data=date(2024, 3, 20),
            valor=Decimal("800.00"),
            tipo=TipoMovimentacao.DEBITO,
            historico="Débito fictício de material",
            identificador="MOV-DEMO-1001",
            demonstracao=True,
        )
        movimento.pagamentos.add(pagamento)
        Contrapartida.objects.create(
            prestacao=prestacao,
            item_plano=item_pessoal,
            descricao="Contrapartida fictícia em bens",
            valor=Decimal("200.00"),
            data=date(2024, 2, 1),
            demonstracao=True,
        )
        Devolucao.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            data=date(2024, 6, 28),
            valor=Decimal("50.00"),
            motivo="Devolução fictícia de saldo",
            demonstracao=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Cenário de demonstração criado: {PROCESSO}"))
