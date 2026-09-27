from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from aplicacao.achados.models import Achado, AchadoEvidencia, Evidencia, RevisaoAchado
from aplicacao.achados.revisao import ErroRevisao, revisar
from aplicacao.usuarios.acesso import pode_consultar


class PodeConsultar(BasePermission):
    def has_permission(self, request, view) -> bool:
        return pode_consultar(request.user)


class EvidenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidencia
        fields = [
            "id",
            "codigo",
            "tipo",
            "origem",
            "documento",
            "pagina_documento",
            "execucao_regra",
            "trecho",
            "valor_textual",
            "valor_numerico",
            "hash_origem",
            "metodo_obtencao",
            "confiabilidade_origem",
            "status_validacao",
            "criada_em",
        ]


class RevisaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevisaoAchado
        fields = ["id", "acao", "status_anterior", "status_novo", "justificativa", "comentario", "usuario", "data_hora"]


class AchadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achado
        fields = [
            "id",
            "codigo",
            "prestacao_contas",
            "titulo",
            "descricao_factual",
            "interpretacao",
            "possivel_implicacao",
            "natureza",
            "tipo_constatacao",
            "status",
            "origem_geracao",
            "materialidade_financeira",
            "criticidade",
            "prioridade",
            "requer_analista",
            "evidencia_insuficiente",
            "criado_em",
            "atualizado_em",
        ]


class EvidenciaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EvidenciaSerializer
    permission_classes = [PodeConsultar]
    queryset = Evidencia.objects.all()


class AchadoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AchadoSerializer
    permission_classes = [PodeConsultar]
    queryset = Achado.objects.all()

    @action(detail=True, methods=["get"])
    def evidencias(self, request, pk=None):
        achado = self.get_object()
        vinculos = AchadoEvidencia.objects.filter(achado=achado).select_related("evidencia")
        dados = []
        for vinculo in vinculos:
            item = EvidenciaSerializer(vinculo.evidencia).data
            item["papel"] = vinculo.papel
            dados.append(item)
        return Response(dados)

    @action(detail=True, methods=["get", "post"])
    def revisoes(self, request, pk=None):
        achado = self.get_object()
        if request.method == "GET":
            return Response(RevisaoSerializer(achado.revisoes.all(), many=True).data)
        try:
            revisao = revisar(
                achado,
                request.user,
                request.data.get("acao", ""),
                justificativa=request.data.get("justificativa", ""),
                comentario=request.data.get("comentario", ""),
            )
        except (ErroRevisao, KeyError) as erro:
            return Response({"detalhe": str(erro)}, status=status.HTTP_403_FORBIDDEN)
        return Response(RevisaoSerializer(revisao).data, status=status.HTTP_201_CREATED)
