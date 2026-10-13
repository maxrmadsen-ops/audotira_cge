from django.urls import path

from aplicacao.usuarios.views_admin import AlternarAtivoUsuarioView, FormularioUsuarioView, ListaUsuariosView

app_name = "usuarios"

urlpatterns = [
    path("administracao/usuarios/", ListaUsuariosView.as_view(), name="lista"),
    path("administracao/usuarios/novo/", FormularioUsuarioView.as_view(), name="novo"),
    path("administracao/usuarios/<int:pk>/", FormularioUsuarioView.as_view(), name="editar"),
    path("administracao/usuarios/<int:pk>/ativo/", AlternarAtivoUsuarioView.as_view(), name="alternar_ativo"),
]
