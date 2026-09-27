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
            self._enriquecer_regras()
            from aplicacao.achados.demonstracao import garantir_demonstracao_achados

            garantir_demonstracao_achados(PrestacaoContas.objects.get(numero_processo=PROCESSO))
            from aplicacao.pareceres.demonstracao import garantir_demonstracao_pre_analise

            garantir_demonstracao_pre_analise(PrestacaoContas.objects.get(numero_processo=PROCESSO))
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
        self._enriquecer_regras()
        from aplicacao.achados.demonstracao import garantir_demonstracao_achados

        garantir_demonstracao_achados(PrestacaoContas.objects.get(numero_processo=PROCESSO))
        from aplicacao.pareceres.demonstracao import garantir_demonstracao_pre_analise

        garantir_demonstracao_pre_analise(PrestacaoContas.objects.get(numero_processo=PROCESSO))
        self.stdout.write(self.style.SUCCESS(f"Cenário de demonstração criado: {PROCESSO}"))

    def _enriquecer_regras(self):
        from aplicacao.documentos.escolhas import OrigemDocumento, TipoDocumento
        from aplicacao.documentos.models import Documento
        from aplicacao.regras.escolhas import FONTE_EXCLUIDA_TESTE_CEGO

        prestacao = PrestacaoContas.objects.get(numero_processo=PROCESSO)
        if prestacao.despesas.filter(descricao="DEMO-REGRAS divergência de valor").exists():
            return
        parcial = prestacao.parciais.order_by("numero_ordem").first()
        fornecedor = prestacao.despesas.exclude(fornecedor=None).first().fornecedor
        divergente = Despesa.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            fornecedor=fornecedor,
            descricao="DEMO-REGRAS divergência de valor",
            valor=Decimal("1000.00"),
            data=date(2024, 4, 2),
            demonstracao=True,
        )
        fiscal = DocumentoFiscal.objects.create(
            prestacao=prestacao,
            emitente=fornecedor,
            tipo=TipoDocumentoFiscal.NOTA_FISCAL,
            numero="1002",
            data_emissao=date(2024, 4, 2),
            valor=Decimal("1000.00"),
            demonstracao=True,
        )
        fiscal.despesas.add(divergente)
        pagamento = Pagamento.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            data=date(2024, 4, 3),
            valor=Decimal("950.00"),
            meio=MeioPagamento.PIX,
            identificador="PIX-DEMO-1002",
            demonstracao=True,
        )
        pagamento.despesas.add(divergente)
        movimento = MovimentacaoBancaria.objects.create(
            prestacao=prestacao,
            data=date(2024, 4, 3),
            valor=Decimal("950.00"),
            tipo=TipoMovimentacao.DEBITO,
            historico="Débito fictício com diferença",
            identificador="MOV-DEMO-1002",
            demonstracao=True,
        )
        movimento.pagamentos.add(pagamento)
        Despesa.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            descricao="DEMO-REGRAS documento ausente",
            valor=Decimal("100.00"),
            data=date(2024, 5, 2),
            demonstracao=True,
        )
        Despesa.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            descricao="DEMO-REGRAS dados insuficientes",
            demonstracao=True,
        )
        fora = Despesa.objects.create(
            prestacao=prestacao,
            prestacao_parcial=parcial,
            descricao="DEMO-REGRAS fora da vigência",
            valor=Decimal("10.00"),
            data=date(2023, 6, 1),
            demonstracao=True,
        )
        fiscal_fora = DocumentoFiscal.objects.create(
            prestacao=prestacao,
            emitente=fornecedor,
            tipo=TipoDocumentoFiscal.NOTA_FISCAL,
            numero="1003",
            data_emissao=date(2023, 6, 1),
            valor=Decimal("10.00"),
            demonstracao=True,
        )
        fiscal_fora.despesas.add(fora)
        Documento.objects.create(
            prestacao_contas=prestacao,
            nome_original="Termo de demonstração.pdf",
            nome_armazenado="termo-demonstracao.pdf",
            tipo_documento=TipoDocumento.TERMO,
            origem=OrigemDocumento.DEMONSTRACAO,
            demonstracao=True,
        )
        Documento.objects.create(
            prestacao_contas=prestacao,
            nome_original="Relatório de prestação final com análise técnica.pdf",
            nome_armazenado="relatorio-analise-tecnica.pdf",
            tipo_documento=TipoDocumento.PRESTACAO_FINAL,
            subtipo_documento=FONTE_EXCLUIDA_TESTE_CEGO,
            origem=OrigemDocumento.DEMONSTRACAO,
            demonstracao=True,
        )
