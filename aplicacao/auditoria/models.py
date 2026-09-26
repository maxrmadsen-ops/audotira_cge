from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    """Trilha dos eventos relevantes: autenticação e mutações do domínio."""

    class Evento(models.TextChoices):
        LOGIN = "login", "Login"
        FALHA_LOGIN = "falha_login", "Falha de login"
        SAIDA = "saida", "Saída"
        UPLOAD = "upload", "Upload"
        EXCLUSAO = "exclusao", "Exclusão"
        CLASSIFICACAO = "classificacao", "Classificação"
        RECLASSIFICACAO = "reclassificacao", "Reclassificação"
        EXECUCAO_REGRA = "execucao_regra", "Execução de regra"
        CHAMADA_IA = "chamada_ia", "Chamada de IA"
        MUDANCA_CONFIGURACAO = "mudanca_configuracao", "Mudança de configuração"
        MUDANCA_PROMPT = "mudanca_prompt", "Mudança de prompt"
        MUDANCA_REGRA = "mudanca_regra", "Mudança de regra"
        REVISAO_HUMANA = "revisao_humana", "Revisão humana"
        GERACAO_PRE_ANALISE = "geracao_pre_analise", "Geração de pré-análise"
        EXPORTACAO = "exportacao", "Exportação"
        CRIACAO = "criacao", "Criação"
        ALTERACAO = "alteracao", "Alteração"

    data_hora = models.DateTimeField("data e hora", auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registros_auditoria",
    )
    evento = models.CharField("evento", max_length=40, choices=Evento.choices, db_index=True)
    descricao = models.TextField("descrição", blank=True)
    endereco_ip = models.GenericIPAddressField("endereço IP", null=True, blank=True)
    caminho = models.CharField("caminho", max_length=255, blank=True)
    detalhes = models.JSONField("detalhes", default=dict, blank=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        ordering = ["-data_hora"]

    def __str__(self) -> str:
        return f"{self.get_evento_display()} em {self.data_hora:%d/%m/%Y %H:%M}"
