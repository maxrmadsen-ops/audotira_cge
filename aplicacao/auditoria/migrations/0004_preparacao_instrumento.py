from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0003_perfis_responsabilidade"),
    ]

    operations = [
        migrations.AlterField(
            model_name="registroauditoria",
            name="evento",
            field=models.CharField(
                choices=[
                    ("login", "Login"),
                    ("falha_login", "Falha de login"),
                    ("saida", "Saída"),
                    ("upload", "Upload"),
                    ("exclusao", "Exclusão"),
                    ("classificacao", "Classificação"),
                    ("reclassificacao", "Reclassificação"),
                    ("execucao_regra", "Execução de regra"),
                    ("chamada_ia", "Chamada de IA"),
                    ("mudanca_configuracao", "Mudança de configuração"),
                    ("mudanca_prompt", "Mudança de prompt"),
                    ("mudanca_regra", "Mudança de regra"),
                    ("revisao_humana", "Revisão humana"),
                    ("geracao_pre_analise", "Geração de pré-análise"),
                    ("exportacao", "Exportação"),
                    ("criacao", "Criação"),
                    ("alteracao", "Alteração"),
                    ("processamento", "Processamento"),
                    ("erro_processamento", "Erro de processamento"),
                    ("reprocessamento", "Reprocessamento"),
                    ("validacao_humana", "Validação humana"),
                    ("consulta_normativa", "Consulta normativa"),
                    ("ground_truth", "Ground Truth"),
                    ("avaliacao_ia", "Avaliação IA × técnico"),
                    ("atribuicao_processo", "Atribuição de processo"),
                    ("redistribuicao_processo", "Redistribuição de processo"),
                    ("mudanca_usuario", "Mudança de usuário"),
                    ("mudanca_perfil", "Mudança de perfil"),
                    ("abertura_diligencia", "Abertura de diligência"),
                    ("alteracao_diligencia", "Alteração de diligência"),
                    ("elaboracao_parecer", "Elaboração de parecer"),
                    ("instrumento_selecionado", "Instrumento selecionado"),
                    ("instrumento_processado", "Instrumento processado"),
                    ("instrumento_classificado", "Instrumento classificado"),
                    ("campo_confirmado", "Campo confirmado"),
                    ("campo_corrigido", "Campo corrigido"),
                    ("campo_nao_identificado", "Campo não identificado"),
                    ("validacao_instrumento_concluida", "Validação do instrumento concluída"),
                    ("validacao_instrumento_reaberta", "Validação do instrumento reaberta"),
                    ("instrumento_reprocessado", "Instrumento reprocessado"),
                ],
                db_index=True,
                max_length=40,
                verbose_name="evento",
            ),
        ),
    ]
