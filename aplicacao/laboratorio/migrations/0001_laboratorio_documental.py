import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("documentos", "0002_fundamento_classificacao"),
        ("prestacoes_contas", "0004_estado_revisao_e_campos_monetarios"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LoteLaboratorio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_processo_parcial", models.CharField(max_length=60, verbose_name="processo da prestação parcial")),
                ("numero_instrumento", models.CharField(blank=True, max_length=80, verbose_name="instrumento correspondente")),
                (
                    "estado_conferencia_instrumento",
                    models.CharField(
                        choices=[("pendente", "Conferência pendente"), ("confirmada", "Conferência humana registrada")],
                        default="pendente",
                        max_length=20,
                        verbose_name="estado da conferência do instrumento",
                    ),
                ),
                ("origem", models.CharField(blank=True, max_length=255, verbose_name="origem do arquivo")),
                ("hash_sha256", models.CharField(db_index=True, max_length=64, verbose_name="SHA-256 do original")),
                ("tamanho_bytes", models.PositiveBigIntegerField(default=0, verbose_name="tamanho em bytes")),
                ("quantidade_paginas", models.PositiveIntegerField(default=0, verbose_name="quantidade de páginas")),
                ("tecnica_predominante", models.CharField(blank=True, max_length=40, verbose_name="técnica predominante")),
                ("limitacoes", models.TextField(blank=True, verbose_name="limitações registradas")),
                ("importado_em", models.DateTimeField(auto_now_add=True, verbose_name="importado em")),
                ("processado_em", models.DateTimeField(blank=True, null=True, verbose_name="processado em")),
                ("duracao_processamento_ms", models.PositiveIntegerField(blank=True, null=True, verbose_name="duração do processamento (ms)")),
                (
                    "documento",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lote_laboratorio",
                        to="documentos.documento",
                        verbose_name="documento original",
                    ),
                ),
                (
                    "importado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lotes_laboratorio_importados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="importado por",
                    ),
                ),
                (
                    "prestacao_parceria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lotes_laboratorio",
                        to="prestacoes_contas.prestacaocontas",
                        verbose_name="processo da parceria",
                    ),
                ),
            ],
            options={
                "verbose_name": "lote do laboratório",
                "verbose_name_plural": "lotes do laboratório",
                "ordering": ["-importado_em"],
            },
        ),
        migrations.CreateModel(
            name="InventarioPagina",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_fisico", models.PositiveIntegerField(verbose_name="número físico no PDF")),
                ("numero_impresso", models.CharField(blank=True, max_length=40, verbose_name="número impresso")),
                ("tipos_candidatos", models.JSONField(blank=True, default=list, verbose_name="tipos documentais candidatos")),
                ("quantidade_regioes", models.PositiveIntegerField(default=0, verbose_name="quantidade de regiões")),
                ("tem_texto_digital", models.BooleanField(default=False, verbose_name="possui texto digital")),
                ("tem_imagem", models.BooleanField(default=True, verbose_name="possui conteúdo de imagem")),
                (
                    "qualidade_extracao",
                    models.CharField(
                        choices=[
                            ("suficiente", "Suficiente"),
                            ("insuficiente", "Insuficiente"),
                            ("ausente", "Ausente"),
                            ("ilegivel", "Ilegível"),
                        ],
                        default="ausente",
                        max_length=20,
                        verbose_name="qualidade da extração",
                    ),
                ),
                ("legibilidade", models.CharField(blank=True, max_length=40, verbose_name="indicador de legibilidade")),
                (
                    "tecnica_utilizada",
                    models.CharField(
                        blank=True,
                        choices=[("nativo", "Nativo"), ("ocr", "OCR"), ("hibrido", "Híbrido"), ("sem_texto", "Sem texto")],
                        max_length=20,
                        verbose_name="técnica utilizada",
                    ),
                ),
                ("tecnica_recomendada", models.CharField(blank=True, max_length=40, verbose_name="técnica recomendada")),
                (
                    "estado_classificacao",
                    models.CharField(
                        choices=[
                            ("inconclusivo", "Sem classificação conclusiva"),
                            ("proposto", "Proposta automática"),
                            ("confirmado", "Classificação confirmada"),
                            ("corrigido", "Classificação corrigida"),
                        ],
                        default="inconclusivo",
                        max_length=20,
                        verbose_name="estado da classificação",
                    ),
                ),
                (
                    "estado_revisao",
                    models.CharField(
                        choices=[
                            ("pendente", "Revisão pendente"),
                            ("revisada", "Revisão registrada"),
                            ("ilegivel", "Marcada como ilegível"),
                            ("reprocessar", "Reprocessamento solicitado"),
                        ],
                        default="pendente",
                        max_length=20,
                        verbose_name="estado da revisão humana",
                    ),
                ),
                ("quantidade_caracteres", models.PositiveIntegerField(default=0, verbose_name="quantidade de caracteres")),
                ("trecho_amostra", models.CharField(blank=True, max_length=280, verbose_name="trecho de amostra")),
                ("proveniencia", models.CharField(blank=True, max_length=255, verbose_name="evidência de proveniência")),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="paginas",
                        to="laboratorio.lotelaboratorio",
                        verbose_name="lote",
                    ),
                ),
                (
                    "pagina_documento",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="inventarios_laboratorio",
                        to="documentos.paginadocumento",
                        verbose_name="página do documento",
                    ),
                ),
            ],
            options={
                "verbose_name": "página inventariada",
                "verbose_name_plural": "páginas inventariadas",
                "ordering": ["numero_fisico"],
            },
        ),
        migrations.CreateModel(
            name="RegiaoDocumental",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo_documental",
                    models.CharField(
                        choices=[
                            ("checklist_documental", "Checklist documental"),
                            ("oficio_encaminhamento", "Ofício de encaminhamento"),
                            ("relatorio_execucao_objeto", "Relatório de execução do objeto"),
                            ("balancete", "Balancete"),
                            ("comprovante_transferencia", "Comprovante de transferência"),
                            ("holerite", "Holerite / demonstrativo de pagamento"),
                            ("folha_pagamento", "Folha de pagamento"),
                            ("termo_rescisao", "Termo de rescisão de contrato de trabalho"),
                            ("termo_quitacao", "Termo de quitação"),
                            ("comunicacao_dispensa", "Comunicação de dispensa"),
                            ("guia_fgts", "Guia de FGTS"),
                            ("comprovante_fgts", "Comprovante de recolhimento de FGTS"),
                            ("extrato_bancario", "Extrato bancário"),
                            ("administrativo_sgpe", "Documento administrativo do SGP-e"),
                            ("assinaturas_autenticacoes", "Assinaturas e autenticações"),
                            ("outros_nao_classificados", "Outros / não classificados"),
                        ],
                        max_length=60,
                        verbose_name="tipo documental",
                    ),
                ),
                ("ordem", models.PositiveIntegerField(default=1, verbose_name="ordem na página")),
                ("x", models.FloatField(default=0.0, verbose_name="x relativo")),
                ("y", models.FloatField(default=0.0, verbose_name="y relativo")),
                ("largura", models.FloatField(default=1.0, verbose_name="largura relativa")),
                ("altura", models.FloatField(default=1.0, verbose_name="altura relativa")),
                ("metodo_deteccao", models.CharField(blank=True, max_length=60, verbose_name="método de detecção")),
                ("confianca", models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, verbose_name="confiança")),
                ("versao_classificacao", models.PositiveIntegerField(default=1, verbose_name="versão da classificação")),
                (
                    "estado_classificacao",
                    models.CharField(
                        choices=[
                            ("inconclusivo", "Sem classificação conclusiva"),
                            ("proposto", "Proposta automática"),
                            ("confirmado", "Classificação confirmada"),
                            ("corrigido", "Classificação corrigida"),
                        ],
                        default="proposto",
                        max_length=20,
                        verbose_name="estado da classificação",
                    ),
                ),
                (
                    "estado_revisao",
                    models.CharField(
                        choices=[
                            ("pendente", "Revisão pendente"),
                            ("revisada", "Revisão registrada"),
                            ("ilegivel", "Marcada como ilegível"),
                            ("reprocessar", "Reprocessamento solicitado"),
                        ],
                        default="pendente",
                        max_length=20,
                        verbose_name="estado da revisão",
                    ),
                ),
                ("justificativa", models.TextField(blank=True, verbose_name="justificativa da revisão")),
                ("revisado_em", models.DateTimeField(blank=True, null=True, verbose_name="revisado em")),
                ("grupo_peca", models.CharField(blank=True, max_length=80, verbose_name="identificador da peça multipágina")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="regioes",
                        to="laboratorio.lotelaboratorio",
                        verbose_name="lote",
                    ),
                ),
                (
                    "pagina",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="regioes",
                        to="laboratorio.inventariopagina",
                        verbose_name="página",
                    ),
                ),
                (
                    "revisado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="regioes_laboratorio_revisadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="revisado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "região documental",
                "verbose_name_plural": "regiões documentais",
                "ordering": ["pagina__numero_fisico", "ordem", "id"],
            },
        ),
        migrations.CreateModel(
            name="CampoExtraido",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("esquema", models.CharField(max_length=40, verbose_name="esquema tipado")),
                ("chave", models.CharField(max_length=80, verbose_name="chave do campo")),
                ("rotulo", models.CharField(max_length=120, verbose_name="rótulo")),
                ("valor_original", models.TextField(blank=True, verbose_name="valor original")),
                ("valor_normalizado", models.TextField(blank=True, verbose_name="valor normalizado")),
                ("numero_pagina", models.PositiveIntegerField(verbose_name="página física")),
                ("trecho_evidencia", models.TextField(blank=True, verbose_name="trecho de evidência")),
                ("metodo", models.CharField(blank=True, max_length=60, verbose_name="método")),
                ("estado_confianca", models.CharField(blank=True, max_length=40, verbose_name="estado de confiança")),
                (
                    "estado_revisao",
                    models.CharField(
                        choices=[
                            ("pendente", "Extração pendente de revisão"),
                            ("confirmado", "Extração confirmada"),
                            ("corrigido", "Extração corrigida"),
                            ("ausente", "Não localizado na evidência"),
                        ],
                        default="pendente",
                        max_length=20,
                        verbose_name="estado da revisão",
                    ),
                ),
                ("obrigatorio", models.BooleanField(default=False, verbose_name="campo obrigatório no esquema")),
                ("historico_correcoes", models.JSONField(blank=True, default=list, verbose_name="histórico de correções")),
                ("revisado_em", models.DateTimeField(blank=True, null=True, verbose_name="revisado em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                (
                    "regiao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="campos",
                        to="laboratorio.regiaodocumental",
                        verbose_name="região",
                    ),
                ),
                (
                    "revisado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="campos_laboratorio_revisados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="revisado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "campo extraído",
                "verbose_name_plural": "campos extraídos",
                "ordering": ["regiao_id", "chave", "id"],
            },
        ),
        migrations.CreateModel(
            name="VinculoEvidencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_vinculo", models.CharField(max_length=60, verbose_name="tipo de vínculo")),
                ("criterios", models.JSONField(blank=True, default=list, verbose_name="critérios utilizados")),
                ("divergencias", models.JSONField(blank=True, default=list, verbose_name="divergências observadas")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("sugerido", "Vínculo sugerido"),
                            ("confirmado", "Vínculo confirmado"),
                            ("rejeitado", "Vínculo rejeitado"),
                        ],
                        default="sugerido",
                        max_length=20,
                        verbose_name="estado de confirmação",
                    ),
                ),
                ("justificativa", models.TextField(blank=True, verbose_name="justificativa")),
                ("revisado_em", models.DateTimeField(blank=True, null=True, verbose_name="revisado em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                (
                    "destino",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vinculos_destino",
                        to="laboratorio.regiaodocumental",
                        verbose_name="região de destino",
                    ),
                ),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vinculos",
                        to="laboratorio.lotelaboratorio",
                        verbose_name="lote",
                    ),
                ),
                (
                    "origem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vinculos_origem",
                        to="laboratorio.regiaodocumental",
                        verbose_name="região de origem",
                    ),
                ),
                (
                    "revisado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vinculos_laboratorio_revisados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="revisado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "vínculo entre evidências",
                "verbose_name_plural": "vínculos entre evidências",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="PendenciaDocumental",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("motivo", models.TextField(verbose_name="motivo")),
                (
                    "prioridade",
                    models.CharField(
                        choices=[("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta")],
                        default="media",
                        max_length=20,
                        verbose_name="prioridade",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("aberta", "Aberta"),
                            ("em_preparacao", "Solicitação em preparação"),
                            ("resolvida", "Resolvida"),
                        ],
                        default="aberta",
                        max_length=20,
                        verbose_name="status",
                    ),
                ),
                ("solicitacao_esclarecimento", models.TextField(blank=True, verbose_name="solicitação de esclarecimento preparada")),
                ("historico", models.JSONField(blank=True, default=list, verbose_name="histórico")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                (
                    "campo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pendencias",
                        to="laboratorio.campoextraido",
                        verbose_name="campo",
                    ),
                ),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pendencias",
                        to="laboratorio.lotelaboratorio",
                        verbose_name="lote",
                    ),
                ),
                (
                    "pagina",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pendencias",
                        to="laboratorio.inventariopagina",
                        verbose_name="página",
                    ),
                ),
                (
                    "regiao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pendencias",
                        to="laboratorio.regiaodocumental",
                        verbose_name="peça",
                    ),
                ),
                (
                    "responsavel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pendencias_laboratorio",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="responsável",
                    ),
                ),
            ],
            options={
                "verbose_name": "pendência documental",
                "verbose_name_plural": "pendências documentais",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="RevisaoLaboratorio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alvo", models.CharField(max_length=40, verbose_name="alvo da revisão")),
                ("alvo_id", models.PositiveIntegerField(verbose_name="identificador do alvo")),
                ("acao", models.CharField(max_length=60, verbose_name="ação")),
                ("justificativa", models.TextField(blank=True, verbose_name="justificativa")),
                ("detalhe", models.JSONField(blank=True, default=dict, verbose_name="detalhe")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisoes",
                        to="laboratorio.lotelaboratorio",
                        verbose_name="lote",
                    ),
                ),
                (
                    "responsavel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revisoes_laboratorio",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="responsável",
                    ),
                ),
            ],
            options={
                "verbose_name": "revisão do laboratório",
                "verbose_name_plural": "revisões do laboratório",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="inventariopagina",
            constraint=models.UniqueConstraint(fields=("lote", "numero_fisico"), name="lab_pagina_unica_no_lote"),
        ),
    ]
