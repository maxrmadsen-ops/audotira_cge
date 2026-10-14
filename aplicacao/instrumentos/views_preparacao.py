from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.auditoria.servicos import obter_ip, registrar_evento
from aplicacao.documentos.ficha import montar_ficha
from aplicacao.instrumentos.conferencia import (
    confirmar_lote,
    contagem_divergencias,
    destino_conferencia,
    elegiveis_instrumento,
    ler_volta,
    montar_grupos,
    modalidades_por_campo,
    navegacao_processo,
    secoes_complementares,
)
from aplicacao.instrumentos.escolhas import EstadoPreparacao
from aplicacao.documentos.models import Documento
from aplicacao.documentos.recebimento import receber_arquivo
from aplicacao.documentos.validacao import ErroValidacaoDocumento
from aplicacao.instrumentos.models import TermoCongelado
from aplicacao.instrumentos.preparacao import (
    concluir_validacao,
    obter_preparacao,
    processar_instrumento,
    reabrir_validacao,
    selecionar_documento,
    situacao_referencia,
)
from aplicacao.instrumentos.servico import termo_do_documento
from aplicacao.instrumentos.esquema_partes import ROTULO_UNIDADE, confirmar_parte, corrigir_atributo_parte, montar_unidades
from aplicacao.instrumentos.base_normativa import (
    adicionar_documento,
    conferir_documento,
    grupo_da_referencia,
    informar_datas,
    mensagem_resumo,
    montar_linhas,
    registrar_divergencia_vigencia,
    resumo_linhas,
    situacao_atual,
    substituir_documento,
    validar_referencia,
    verificar_vigencia,
)
from aplicacao.normas.escolhas import NaturezaDocumentoNormativo, RedacaoRepresentada
from aplicacao.instrumentos.estruturacao_partes import estruturar_partes
from aplicacao.instrumentos.unidade_identificacao import confirmar_identificacao, corrigir_atributo_identificacao
from aplicacao.instrumentos.unidade_objeto import (
    NOME_UNIDADE,
    confirmar_unidade,
    corrigir_unidade,
    divergir_unidade,
    progresso_da_conferencia,
    unidade_elegivel_lote,
)
from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import exigir_atuar_na_prestacao, exigir_ver_prestacao, pode_atuar_na_prestacao
from aplicacao.usuarios.models import Usuario

PERFIS = (
    Usuario.Perfil.ADMINISTRADOR,
    Usuario.Perfil.AUDITOR,
    Usuario.Perfil.ANALISTA,
)

PASSOS_FUTUROS = (
    (2, "Base Normativa"),
    (3, "Entidade"),
    (4, "Plano de Trabalho"),
)


class _PreparacaoMixin:
    def _prestacao(self, request, pk):
        if not request.user.is_authenticated or request.user.perfil not in PERFIS:
            raise PermissionDenied("Sem permissão para a preparação da análise.")
        prestacao = get_object_or_404(PrestacaoContas, pk=pk)
        exigir_ver_prestacao(request.user, prestacao)
        return prestacao

    def _atuar(self, request, prestacao):
        exigir_atuar_na_prestacao(request.user, prestacao)

    def _navegacao(self, prestacao, preparacao, atividade):
        return navegacao_processo(
            atividade,
            preparacao.get_estado_display(),
            reverse("instrumentos:instrumento", args=[prestacao.pk]),
            url_base=reverse("instrumentos:base_normativa", args=[prestacao.pk]),
            base_disponivel=preparacao.estado == EstadoPreparacao.VALIDADO,
        )


class PreparacaoAnaliseView(_PreparacaoMixin, View):
    def get(self, request, pk):
        prestacao = self._prestacao(request, pk)
        preparacao = obter_preparacao(prestacao)
        return render(
            request,
            "instrumentos/preparacao.html",
            {
                "prestacao": prestacao,
                "preparacao": preparacao,
                "passos_futuros": PASSOS_FUTUROS,
                "navegacao": self._navegacao(prestacao, preparacao, "preparacao"),
                "pode_preparar": pode_atuar_na_prestacao(request.user, prestacao),
            },
        )


class InstrumentoParceriaView(_PreparacaoMixin, View):
    def get(self, request, pk):
        prestacao = self._prestacao(request, pk)
        return render(request, "instrumentos/instrumento.html", self._contexto(request, prestacao))

    def post(self, request, pk):
        prestacao = self._prestacao(request, pk)
        self._atuar(request, prestacao)
        preparacao = obter_preparacao(prestacao)
        acao = request.POST.get("acao", "")
        try:
            if acao == "selecionar":
                documento = get_object_or_404(
                    Documento.objects.ativos(),
                    pk=request.POST.get("documento"),
                    prestacao_contas=prestacao,
                )
                selecionar_documento(preparacao, documento, request.user)
                messages.success(request, "Instrumento selecionado.")
            elif acao == "enviar":
                if request.POST.get("confirmar_envio") != "1":
                    raise ValueError("O envio do instrumento exige confirmação explícita.")
                arquivo = request.FILES.get("arquivo")
                if arquivo is None:
                    raise ValueError("Envie o arquivo do instrumento.")
                documento, _ = receber_arquivo(prestacao=prestacao, arquivo=arquivo, usuario=request.user, request=request)
                selecionar_documento(preparacao, documento, request.user)
                self._avisar_processamento(request, processar_instrumento(preparacao, request.user))
            elif acao == "processar":
                reprocessar = request.POST.get("reprocessar") == "1"
                if reprocessar and request.POST.get("confirmar_reprocessar") != "1":
                    raise ValueError("O reprocessamento exige confirmação explícita. Uma versão congelada não é apagada.")
                self._avisar_processamento(
                    request,
                    processar_instrumento(preparacao, request.user, reprocessar=reprocessar),
                )
            elif acao == "confirmar_lote":
                self._confirmar_lote(request, preparacao)
            elif acao == "confirmar_unidade":
                self._registrar_unidade(request, preparacao, "confirmar")
            elif acao == "corrigir_unidade":
                self._registrar_unidade(request, preparacao, "corrigir")
            elif acao == "divergir_unidade":
                self._registrar_unidade(request, preparacao, "divergir")
            elif acao == "confirmar_parte":
                self._registrar_parte(request, preparacao, "confirmar")
            elif acao == "corrigir_atributo_parte":
                self._registrar_parte(request, preparacao, "corrigir")
            elif acao == "confirmar_identificacao":
                self._registrar_identificacao(request, preparacao, "confirmar")
            elif acao == "corrigir_atributo_identificacao":
                self._registrar_identificacao(request, preparacao, "corrigir")
            elif acao == "estruturar_partes":
                self._estruturar_partes(request, preparacao)
            elif acao == "concluir":
                concluir_validacao(preparacao, request.user, ciente_ausencias=request.POST.get("ciente_ausencias") == "1")
                messages.success(request, "Validação do instrumento concluída pelo usuário. O passo 1 está validado.")
            elif acao == "reabrir":
                reabrir_validacao(preparacao, request.user)
                messages.success(request, "Validação reaberta em nova versão. A versão anterior permanece.")
            else:
                messages.error(request, "Ação não reconhecida.")
        except (TermoCongelado, ValidationError, ValueError, ErroValidacaoDocumento) as exc:
            messages.error(request, getattr(exc, "mensagem", None) or (exc.messages[0] if getattr(exc, "messages", None) else str(exc)))
        return redirect(destino_conferencia(reverse("instrumentos:instrumento", args=[prestacao.pk]), request))

    def _avisar_processamento(self, request, preparacao):
        preparacao.refresh_from_db()
        if preparacao.estado == EstadoPreparacao.ERRO:
            messages.error(request, preparacao.mensagem or "O processamento do instrumento falhou.")
            return
        messages.success(request, "Processamento concluído. A revisão humana continua obrigatória.")

    def _confirmar_lote(self, request, preparacao):
        if request.POST.get("confirmar_lote") != "1":
            raise ValueError("A confirmação em lote exige confirmação explícita do usuário.")
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        if termo is None:
            raise ValueError("Processe o instrumento antes de confirmar campos.")
        escopo = request.POST.get("escopo", "")
        if escopo == "instrumento":
            nomes = None
            modalidade = "lote_instrumento"
            incluir_unidade = True
        elif escopo == "grupo":
            nomes = request.POST.getlist("campo")
            if not nomes:
                raise ValueError("Nenhum campo elegível foi indicado para este grupo.")
            modalidade = "lote_grupo"
            incluir_unidade = NOME_UNIDADE in nomes
            nomes = [nome for nome in nomes if nome != NOME_UNIDADE]
        else:
            raise ValueError("A confirmação em lote precisa indicar o grupo ou o instrumento.")
        confirmados = confirmar_lote(termo, request.user, nomes)
        if incluir_unidade and unidade_elegivel_lote(termo):
            confirmados.append(confirmar_unidade(termo, request.user, modalidade))
        for campo in confirmados:
            registrar_evento(
                evento=RegistroAuditoria.Evento.CAMPO_CONFIRMADO,
                descricao="Validação humana de campo do instrumento",
                usuario=request.user,
                endereco_ip=obter_ip(request),
                caminho=request.path,
                detalhes={
                    "documento": documento.pk,
                    "prestacao": preparacao.prestacao_id,
                    "campo": campo.nome,
                    "status": campo.status,
                    "versao": termo.versao,
                    "valor_extraido": campo.valor_extraido,
                    "valor_validado": campo.valor_validado,
                    "modalidade": getattr(campo, "modalidade_gravada", modalidade),
                    "unidade": "objeto_finalidade" if campo.nome == NOME_UNIDADE else "",
                    "clausula": getattr(campo, "clausula_rotulo", ""),
                    "justificativa": campo.observacao,
                },
            )
        if confirmados:
            messages.success(
                request,
                f"{len(confirmados)} campo(s) confirmado(s). Correções, ausências, validações anteriores e divergências foram preservadas.",
            )
            return
        messages.info(request, "Nenhum campo elegível para confirmação em lote. Os demais registros foram preservados.")

    def _registrar_unidade(self, request, preparacao, acao):
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        if termo is None:
            raise ValueError("Processe o instrumento antes de validar a cláusula.")
        if acao == "confirmar":
            campo = confirmar_unidade(termo, request.user)
            evento = RegistroAuditoria.Evento.CAMPO_CONFIRMADO
            messages.success(request, "Cláusula confirmada. Os atributos técnicos permanecem como foram extraídos.")
        elif acao == "corrigir":
            campo = corrigir_unidade(
                termo,
                request.user,
                request.POST.get("valor_validado", ""),
                request.POST.get("observacao", ""),
            )
            evento = RegistroAuditoria.Evento.CAMPO_CORRIGIDO
            messages.success(request, "Correção da cláusula registrada. O texto extraído e os atributos técnicos permanecem.")
        else:
            campo = divergir_unidade(termo, request.user, request.POST.get("observacao", ""))
            evento = RegistroAuditoria.Evento.VALIDACAO_HUMANA
            messages.success(request, "Divergência da cláusula registrada. As validações anteriores dos atributos permanecem.")
        registrar_evento(
            evento=evento,
            descricao="Validação humana da cláusula de objeto e finalidade",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "documento": documento.pk,
                "prestacao": preparacao.prestacao_id,
                "campo": campo.nome,
                "unidade": "objeto_finalidade",
                "clausula": campo.clausula_rotulo,
                "status": campo.status,
                "versao": termo.versao,
                "valor_extraido": campo.valor_extraido,
                "valor_validado": campo.valor_validado,
                "modalidade": "individual",
                "justificativa": campo.observacao,
            },
        )

    def _registrar_parte(self, request, preparacao, acao):
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        if termo is None:
            raise ValueError("Processe o instrumento antes de validar a parte.")
        papel = request.POST.get("papel", "")
        rotulo = ROTULO_UNIDADE.get(papel, papel)
        if acao == "confirmar":
            gravados = confirmar_parte(termo, request.user, papel)
            por_nome = {campo.nome: campo for campo in termo.campos.all()}
            unidade = next(item for item in montar_unidades(termo, por_nome) if item["papel"] == papel)
            messages.success(
                request,
                f"{rotulo} confirmado: {len(gravados)} atributos. {len(unidade['ausentes'])} ausências permanecem sem validação.",
            )
            registrar_evento(
                evento=RegistroAuditoria.Evento.CAMPO_CONFIRMADO,
                descricao="Validação humana da unidade de parte",
                usuario=request.user,
                endereco_ip=obter_ip(request),
                caminho=request.path,
                detalhes={
                    "documento": documento.pk,
                    "prestacao": preparacao.prestacao_id,
                    "campo": f"unidade_parte_{papel}",
                    "unidade": papel,
                    "rotulo_unidade": rotulo,
                    "atributos": [
                        {
                            "chave": campo.nome.removeprefix(f"parte_{papel}_"),
                            "rotulo": campo.rotulo,
                            "valor": campo.valor_validado,
                        }
                        for campo in gravados
                    ],
                    "ausentes": [linha["chave"] for linha in unidade["ausentes"]],
                    "status": "validado",
                    "versao": termo.versao,
                    "modalidade": "lote_unidade",
                    "metodo": "parte_existente",
                },
            )
            return
        campo = corrigir_atributo_parte(
            termo,
            request.user,
            papel,
            request.POST.get("chave", ""),
            request.POST.get("valor_validado", ""),
            request.POST.get("observacao", ""),
        )
        messages.success(request, "Correção do atributo registrada. Os demais atributos permanecem.")
        registrar_evento(
            evento=RegistroAuditoria.Evento.CAMPO_CORRIGIDO,
            descricao="Correção humana de atributo da parte",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "documento": documento.pk,
                "prestacao": preparacao.prestacao_id,
                "campo": campo.nome,
                "unidade": papel,
                "rotulo_unidade": rotulo,
                "status": campo.status,
                "versao": termo.versao,
                "valor_extraido": campo.valor_extraido,
                "valor_validado": campo.valor_validado,
                "modalidade": "individual",
                "justificativa": campo.observacao,
            },
        )

    def _estruturar_partes(self, request, preparacao):
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        if termo is None:
            raise ValueError("Processe o instrumento antes de estruturar as partes.")
        resumo = estruturar_partes(termo)
        registrar_evento(
            evento=RegistroAuditoria.Evento.CHAMADA_IA,
            descricao="Estruturação dos atributos de parte a partir do texto do documento",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "documento": documento.pk,
                "prestacao": preparacao.prestacao_id,
                "versao": termo.versao,
                "versao_prompt": resumo.get("versao_prompt"),
                "uso_id": resumo.get("uso_id"),
                "provedor": resumo.get("provedor") or "",
                "modelo": resumo.get("modelo") or "",
                "aceitos": resumo["aceitos"],
                "rejeitados": resumo["rejeitados"],
            },
        )
        if resumo["aceitos"]:
            messages.success(
                request,
                f"{len(resumo['aceitos'])} atributos foram estruturados a partir de trechos do documento. "
                f"{len(resumo['rejeitados'])} respostas ficaram de fora. A conferência humana continua obrigatória.",
            )
            return
        if resumo["rejeitados"]:
            messages.info(
                request,
                "O modelo respondeu, mas esses trechos não estavam no documento como foram devolvidos. "
                "Nenhum campo foi alterado. Os valores já preenchidos e as validações humanas permanecem.",
            )
            return
        messages.info(request, "Nenhum atributo novo foi gravado. Os valores já preenchidos e as validações humanas permanecem.")

    def _registrar_identificacao(self, request, preparacao, acao):
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        if termo is None:
            raise ValueError("Processe o instrumento antes de validar a identificação.")
        if acao == "confirmar":
            gravados = confirmar_identificacao(termo, request.user)
            messages.success(
                request,
                f"Identificação confirmada: {len(gravados)} atributos. Ausências permanecem sem validação.",
            )
            registrar_evento(
                evento=RegistroAuditoria.Evento.CAMPO_CONFIRMADO,
                descricao="Validação humana da identificação do instrumento",
                usuario=request.user,
                endereco_ip=obter_ip(request),
                caminho=request.path,
                detalhes={
                    "documento": documento.pk,
                    "prestacao": preparacao.prestacao_id,
                    "campo": "unidade_identificacao",
                    "unidade": "identificacao",
                    "atributos": [
                        {"chave": campo.nome.removeprefix("idinst_"), "rotulo": campo.rotulo, "valor": campo.valor_validado}
                        for campo in gravados
                    ],
                    "versao": termo.versao,
                    "modalidade": "lote_unidade",
                },
            )
            return
        campo = corrigir_atributo_identificacao(
            termo,
            request.user,
            request.POST.get("chave", ""),
            request.POST.get("valor_validado", ""),
            request.POST.get("observacao", ""),
        )
        messages.success(request, "Correção do atributo registrada. Os demais atributos da identificação permanecem.")
        registrar_evento(
            evento=RegistroAuditoria.Evento.CAMPO_CORRIGIDO,
            descricao="Correção humana de atributo da identificação",
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes={
                "documento": documento.pk,
                "prestacao": preparacao.prestacao_id,
                "campo": campo.nome,
                "unidade": "identificacao",
                "status": campo.status,
                "versao": termo.versao,
                "valor_extraido": campo.valor_extraido,
                "valor_validado": campo.valor_validado,
                "modalidade": "individual",
                "justificativa": campo.observacao,
            },
        )

    def _contexto(self, request, prestacao):
        preparacao = obter_preparacao(prestacao)
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        ficha = montar_ficha(documento, termo) if documento and termo else None
        referencias = []
        grupos = []
        if termo:
            referencias = [
                {"item": item, "situacao": situacao_referencia(item)}
                for item in termo.referencias_normativas.all()
            ]
            grupos = montar_grupos(termo, modalidades_por_campo(prestacao.pk))
        resumo = progresso_da_conferencia(termo)
        resumo["divergencias"] = contagem_divergencias(grupos)
        volta = ler_volta(request)
        return {
            "prestacao": prestacao,
            "preparacao": preparacao,
            "passos_futuros": PASSOS_FUTUROS,
            "navegacao": self._navegacao(prestacao, preparacao, "instrumento"),
            "pode_preparar": pode_atuar_na_prestacao(request.user, prestacao),
            "documentos": prestacao.documentos.ativos().order_by("nome_original"),
            "documento": documento,
            "termo": termo,
            "ficha": ficha,
            "grupos_conferencia": grupos,
            "elegiveis": elegiveis_instrumento(grupos),
            "complementos": secoes_complementares(ficha),
            "resumo": resumo,
            "referencias": referencias,
            "pode_alterar": pode_atuar_na_prestacao(request.user, prestacao),
            "retorno_validacao": reverse("instrumentos:instrumento", args=[prestacao.pk]),
            "pagina_inicial": request.GET.get("pagina") or 1,
            "trecho_inicial": request.GET.get("trecho", ""),
            **volta,
        }


class BaseNormativaView(_PreparacaoMixin, View):
    def get(self, request, pk):
        prestacao = self._prestacao(request, pk)
        preparacao = obter_preparacao(prestacao)
        if preparacao.estado != EstadoPreparacao.VALIDADO:
            messages.info(request, "A Base Normativa abre depois da validação humana do instrumento.")
            return redirect("instrumentos:instrumento", pk=prestacao.pk)
        return render(request, "instrumentos/base_normativa.html", self._contexto(request, prestacao, preparacao))

    def post(self, request, pk):
        prestacao = self._prestacao(request, pk)
        self._atuar(request, prestacao)
        preparacao = obter_preparacao(prestacao)
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        if termo is None or preparacao.estado != EstadoPreparacao.VALIDADO:
            messages.error(request, "Valide o instrumento antes de tratar a base normativa.")
            return redirect("instrumentos:instrumento", pk=prestacao.pk)
        referencia = termo.referencias_normativas.filter(pk=request.POST.get("referencia")).first()
        if referencia is None:
            messages.error(request, "A referência não foi encontrada.")
            return redirect("instrumentos:base_normativa", pk=prestacao.pk)
        acao = request.POST.get("acao", "")
        try:
            linha = grupo_da_referencia(termo, referencia)
            anterior = situacao_atual(linha)
            if acao == "adicionar_documento":
                arquivo = request.FILES.get("arquivo")
                if arquivo is None:
                    raise ValueError("Envie o PDF da norma.")
                documento = adicionar_documento(
                    termo,
                    referencia,
                    arquivo,
                    request.user,
                    natureza=request.POST.get("natureza", ""),
                    redacao=request.POST.get("redacao", ""),
                    fonte=request.POST.get("fonte", ""),
                    identificacao=request.POST.get("identificacao", ""),
                    data_obtencao=request.POST.get("data_obtencao", ""),
                    data_corte=request.POST.get("data_corte", ""),
                    limitacao=request.POST.get("limitacao", ""),
                )
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    documento.norma,
                    RegistroAuditoria.Evento.CRIACAO,
                    "Documento oficial acrescentado à norma",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                    documento=documento,
                )
                messages.success(request, "Documento oficial acrescentado. A conferência deste documento segue pendente.")
            elif acao == "substituir_documento":
                arquivo = request.FILES.get("arquivo")
                if arquivo is None:
                    raise ValueError("Envie o PDF da norma.")
                documento = substituir_documento(
                    termo,
                    referencia,
                    request.POST.get("documento", ""),
                    arquivo,
                    request.user,
                )
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    documento.norma,
                    RegistroAuditoria.Evento.CRIACAO,
                    "Nova versão do documento oficial armazenada",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                    documento=documento,
                )
                messages.success(request, "Nova versão armazenada. A versão anterior e as verificações históricas permanecem.")
            elif acao == "conferir_documento":
                documento = conferir_documento(termo, referencia, request.POST.get("documento", ""), request.user)
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    documento.norma,
                    RegistroAuditoria.Evento.VALIDACAO_HUMANA,
                    "Identificação do documento oficial conferida nesta versão",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                    documento=documento,
                )
                messages.success(request, "Identificação do documento conferida nesta versão.")
            elif acao == "validar":
                validar_referencia(termo, referencia, request.user)
                referencia.refresh_from_db()
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    referencia.norma,
                    RegistroAuditoria.Evento.VALIDACAO_HUMANA,
                    "Identificação da norma conferida pelo auditor",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                )
                messages.success(request, "Identificação conferida. A vigência continua não verificada.")
            elif acao == "informar_datas":
                registro = informar_datas(
                    termo,
                    referencia,
                    request.user,
                    request.POST.get("inicio_vigencia", ""),
                    request.POST.get("fim_vigencia", ""),
                    request.POST.get("fonte_documental", ""),
                    request.POST.get("documento", ""),
                )
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    registro.norma,
                    RegistroAuditoria.Evento.ALTERACAO,
                    "Período de vigência informado, sem verificação conclusiva",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                    registro,
                )
                messages.success(request, "Período informado. A vigência ainda não foi verificada.")
            elif acao == "verificar_vigencia":
                registro = verificar_vigencia(
                    termo,
                    referencia,
                    request.user,
                    request.POST.get("fundamentacao", ""),
                    request.POST.get("data_referencia", ""),
                )
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    registro.norma,
                    RegistroAuditoria.Evento.VALIDACAO_HUMANA,
                    "Vigência verificada pelo auditor, sem concluir a aplicabilidade",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                    registro,
                )
                messages.success(request, "Vigência verificada. A aplicabilidade ao instrumento não foi concluída automaticamente.")
            elif acao == "registrar_divergencia_vigencia":
                registro = registrar_divergencia_vigencia(
                    termo,
                    referencia,
                    request.user,
                    request.POST.get("motivo_divergencia", ""),
                    request.POST.get("data_referencia", ""),
                    request.POST.get("documento", ""),
                )
                self._auditar_base(
                    request,
                    prestacao,
                    referencia,
                    registro.norma,
                    RegistroAuditoria.Evento.VALIDACAO_HUMANA,
                    "Divergência de vigência registrada pelo auditor",
                    acao,
                    anterior,
                    situacao_atual(grupo_da_referencia(termo, referencia)),
                    registro,
                )
                messages.success(request, "Divergência de vigência registrada.")
            else:
                messages.error(request, "Ação não reconhecida.")
        except (ErroValidacaoDocumento, ValidationError, ValueError) as exc:
            messages.error(request, getattr(exc, "mensagem", None) or str(exc))
        return redirect("instrumentos:base_normativa", pk=prestacao.pk)

    def _auditar_base(self, request, prestacao, referencia, norma, evento, descricao, acao, anterior, posterior, registro=None, documento=None):
        detalhes = {
            "prestacao": prestacao.pk,
            "referencia": referencia.pk,
            "norma": getattr(norma, "pk", None),
            "versao": getattr(norma, "versao", None),
            "hash_sha256": getattr(norma, "hash_sha256", ""),
            "acao": acao,
            "situacao_anterior": anterior,
            "situacao_posterior": posterior,
        }
        if documento is not None:
            detalhes.update(
                {
                    "documento": documento.pk,
                    "versao": documento.versao,
                    "hash_sha256": documento.hash_sha256,
                    "natureza": documento.natureza,
                    "redacao": documento.redacao,
                }
            )
        if registro is not None:
            detalhes.update(
                {
                    "estado_vigencia": registro.estado,
                    "versao": registro.versao_documento,
                    "versao_documento": registro.versao_documento,
                    "hash_sha256": registro.hash_sha256,
                    "hash_documento": registro.hash_sha256,
                    "fonte_documental": registro.fonte_documental,
                    "fundamentacao": registro.fundamentacao,
                    "motivo_divergencia": registro.motivo_divergencia,
                    "data_referencia": registro.data_referencia.isoformat() if registro.data_referencia else "",
                    "documento": registro.documento_id,
                }
            )
        registrar_evento(
            evento=evento,
            descricao=descricao,
            usuario=request.user,
            endereco_ip=obter_ip(request),
            caminho=request.path,
            detalhes=detalhes,
        )

    def _processar_norma(self, request, norma):
        try:
            from aplicacao.normas.tarefas import processar_norma_task

            processar_norma_task.delay(norma.id, request.user.id)
        except Exception:
            messages.info(request, "O documento foi armazenado. O processamento em segundo plano não foi iniciado.")

    def _contexto(self, request, prestacao, preparacao):
        documento = preparacao.documento
        termo = termo_do_documento(documento) if documento else None
        linhas = montar_linhas(termo) if termo else []
        resumo = resumo_linhas(linhas)
        return {
            "prestacao": prestacao,
            "preparacao": preparacao,
            "termo": termo,
            "documento": documento,
            "linhas": linhas,
            "resumo_base": resumo,
            "mensagem_base": mensagem_resumo(resumo),
            "navegacao": self._navegacao(prestacao, preparacao, "base"),
            "pode_alterar": pode_atuar_na_prestacao(request.user, prestacao),
            "naturezas_documento": NaturezaDocumentoNormativo.choices,
            "redacoes_documento": RedacaoRepresentada.choices,
        }
