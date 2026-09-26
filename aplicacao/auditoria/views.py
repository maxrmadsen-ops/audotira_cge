from django.views.generic import ListView

from aplicacao.auditoria.models import RegistroAuditoria
from aplicacao.usuarios.acesso import PerfilExigidoMixin
from aplicacao.usuarios.models import Usuario


class ListaRegistrosView(PerfilExigidoMixin, ListView):
    model = RegistroAuditoria
    template_name = "auditoria/registros.html"
    context_object_name = "registros"
    paginate_by = 50
    perfis_permitidos = (Usuario.Perfil.ADMINISTRADOR,)
