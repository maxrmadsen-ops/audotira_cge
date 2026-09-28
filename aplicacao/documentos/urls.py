from django.urls import path

from aplicacao.documentos.views import (
    ArquivarDocumentoView,
    ArquivoDocumentoView,
    DetalheDocumentoView,
    EnviarDocumentosView,
    ExcluirDocumentoView,
    ListaDocumentosView,
    ReprocessarDocumentoView,
    StatusDocumentoView,
    TextoPaginaView,
    ValidarDocumentoView,
)
from aplicacao.instrumentos.views import CongelarTermoView, NovaVersaoTermoView, ValidarCampoTermoView

app_name = "documentos"

urlpatterns = [
    path("documentos/", ListaDocumentosView.as_view(), name="lista"),
    path("prestacoes/<int:prestacao_pk>/documentos/", EnviarDocumentosView.as_view(), name="enviar"),
    path("documentos/<int:pk>/", DetalheDocumentoView.as_view(), name="detalhe"),
    path("documentos/<int:pk>/arquivo/", ArquivoDocumentoView.as_view(), name="arquivo"),
    path("documentos/<int:pk>/status/", StatusDocumentoView.as_view(), name="status"),
    path("documentos/<int:pk>/paginas/<int:numero>/", TextoPaginaView.as_view(), name="texto_pagina"),
    path("documentos/<int:pk>/validar/", ValidarDocumentoView.as_view(), name="validar"),
    path("documentos/<int:pk>/termo/campos/<int:campo_id>/", ValidarCampoTermoView.as_view(), name="validar_campo_termo"),
    path("documentos/<int:pk>/termo/congelar/", CongelarTermoView.as_view(), name="congelar_termo"),
    path("documentos/<int:pk>/termo/nova-versao/", NovaVersaoTermoView.as_view(), name="nova_versao_termo"),
    path("documentos/<int:pk>/reprocessar/", ReprocessarDocumentoView.as_view(), name="reprocessar"),
    path("documentos/<int:pk>/arquivar/", ArquivarDocumentoView.as_view(), name="arquivar"),
    path("documentos/<int:pk>/excluir/", ExcluirDocumentoView.as_view(), name="excluir"),
]
