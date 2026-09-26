from rest_framework import serializers, viewsets
from rest_framework.permissions import BasePermission

from aplicacao.prestacoes_contas.models import PrestacaoContas
from aplicacao.usuarios.acesso import pode_consultar


class PodeConsultar(BasePermission):
    def has_permission(self, request, view) -> bool:
        return pode_consultar(request.user)


class PrestacaoContasSerializer(serializers.ModelSerializer):
    concedente = serializers.StringRelatedField()
    beneficiario = serializers.StringRelatedField()
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
    queryset = PrestacaoContas.objects.select_related("concedente", "beneficiario")
