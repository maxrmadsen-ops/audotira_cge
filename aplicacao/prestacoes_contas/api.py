from rest_framework import serializers, viewsets
from rest_framework.permissions import BasePermission

from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import pode_consultar, pode_ver_prestacao, prestacoes_visiveis


class PodeConsultar(BasePermission):
    def has_permission(self, request, view) -> bool:
        return pode_consultar(request.user)

    def has_object_permission(self, request, view, obj) -> bool:
        return pode_ver_prestacao(request.user, obj)


class PrestacaoContasSerializer(serializers.ModelSerializer):
    concedente = serializers.StringRelatedField()
    beneficiario = serializers.StringRelatedField()
    analista_responsavel = serializers.StringRelatedField()
    numero_instrumento = serializers.CharField(read_only=True)
    tipo_instrumento = serializers.CharField(read_only=True)
    valor_previsto = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True, allow_null=True)
    valor_executado = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True, allow_null=True)

    class Meta:
        model = PrestacaoContas
        fields = [
            "id",
            "numero_processo",
            "numero_instrumento",
            "tipo_instrumento",
            "concedente",
            "beneficiario",
            "analista_responsavel",
            "objeto",
            "valor_total",
            "valor_previsto",
            "valor_executado",
            "data_inicio",
            "data_fim",
            "situacao",
            "fase",
            "demonstracao",
            "criado_em",
            "atualizado_em",
        ]


class PrestacaoContasViewSet(viewsets.ReadOnlyModelViewSet):
    """Consulta da prestação para integrações futuras. Escrita permanece na interface auditada."""

    serializer_class = PrestacaoContasSerializer
    permission_classes = [PodeConsultar]

    def get_queryset(self):
        return prestacoes_visiveis(
            self.request.user,
            PrestacaoContas.objects.select_related("concedente", "beneficiario", "analista_responsavel"),
        )
