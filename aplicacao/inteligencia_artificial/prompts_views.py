from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.inteligencia_artificial.escolhas import StatusVersaoPrompt
from aplicacao.inteligencia_artificial.guardrails import GUARDRAILS_ESTRUTURAIS
from aplicacao.inteligencia_artificial.models import PromptInteligenciaArtificial, VersaoPromptInteligenciaArtificial
from aplicacao.usuarios.acesso import PerfilExigidoMixin, pode_administrar
from aplicacao.usuarios.models import Usuario

PERFIL_LEITURA = (Usuario.Perfil.ADMINISTRADOR, Usuario.Perfil.AUDITOR)
PERFIL_EDICAO = (Usuario.Perfil.ADMINISTRADOR,)
ALERTA = (
    "Alterações neste prompt podem modificar o comportamento da inteligência artificial, "
    "a extração de informações, os resultados das análises e a reprodutibilidade das avaliações. "
    "A alteração será auditada e criará uma nova versão. Deseja continuar?"
)


class ListaPromptsView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_LEITURA

    def get(self, request):
        return render(
            request,
            "inteligencia_artificial/prompts.html",
            {"prompts": PromptInteligenciaArtificial.objects.prefetch_related("versoes")},
        )


class DetalhePromptView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_LEITURA

    def get(self, request, codigo):
        prompt = get_object_or_404(PromptInteligenciaArtificial, codigo=codigo)
        return render(
            request,
            "inteligencia_artificial/prompt_detalhe.html",
            {
                "prompt": prompt,
                "versoes": prompt.versoes.order_by("-versao"),
                "guardrails": GUARDRAILS_ESTRUTURAIS,
                "alerta": ALERTA,
                "pode_editar": pode_administrar(request.user),
            },
        )


class EditarPromptView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_EDICAO

    def post(self, request, codigo):
        prompt = get_object_or_404(PromptInteligenciaArtificial, codigo=codigo)
        if request.POST.get("confirmar_alteracao") != "sim":
            messages.error(request, "A edição exige confirmação explícita do alerta.")
            return redirect("ia:prompt", codigo=codigo)
        justificativa = (request.POST.get("justificativa") or "").strip()
        if not justificativa:
            messages.error(request, "A justificativa é obrigatória.")
            return redirect("ia:prompt", codigo=codigo)
        origem = prompt.versoes.order_by("-versao").first()
        if origem is None:
            messages.error(request, "Não há versão para copiar.")
            return redirect("ia:prompt", codigo=codigo)
        nova = VersaoPromptInteligenciaArtificial(
            prompt=prompt,
            versao=origem.versao + 1,
            prompt_sistema=(request.POST.get("prompt_sistema") or origem.prompt_sistema).strip(),
            template_entrada=(request.POST.get("template_entrada") or origem.template_entrada).strip(),
            schema_saida=origem.schema_saida,
            ativo=False,
            utilizada=False,
            status=StatusVersaoPrompt.RASCUNHO,
            tipo_documental=origem.tipo_documental,
            justificativa=justificativa,
            criado_por=request.user,
        )
        nova.save()
        registrar_evento(
            evento=RegistroAuditoria.Evento.MUDANCA_PROMPT,
            descricao="Nova versão de prompt em rascunho",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={"codigo": codigo, "versao": nova.versao, "hash": nova.hash_conteudo},
        )
        messages.success(request, f"Rascunho v{nova.versao} criado. A versão anterior permanece.")
        return redirect("ia:prompt", codigo=codigo)


class AtivarPromptView(PerfilExigidoMixin, View):
    perfis_permitidos = PERFIL_EDICAO

    def post(self, request, codigo, versao):
        prompt = get_object_or_404(PromptInteligenciaArtificial, codigo=codigo)
        nova = get_object_or_404(VersaoPromptInteligenciaArtificial, prompt=prompt, versao=versao)
        if nova.status == StatusVersaoPrompt.SUBSTITUIDO:
            messages.error(request, "Versão substituída não volta a ficar ativa.")
            return redirect("ia:prompt", codigo=codigo)
        prompt.versoes.filter(ativo=True).exclude(pk=nova.pk).update(ativo=False, status=StatusVersaoPrompt.SUBSTITUIDO)
        nova.status = StatusVersaoPrompt.ATIVO
        nova.ativo = True
        nova.save()
        messages.success(request, f"Versão {nova.versao} ativada.")
        return redirect("ia:prompt", codigo=codigo)
