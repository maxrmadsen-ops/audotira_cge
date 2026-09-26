# Administração

Nesta onda, o perfil `ADMINISTRADOR` acessa:

- Saúde do Sistema, em `/saude/`
- Registros de auditoria, em `/auditoria/registros/`
- Administração técnica do Django, em `/admin/`

Os cadastros de provedores, modelos, preços, agentes, regras, normas, prompts, parâmetros e limites FinOps ficam para a Onda 9. As telas não exibem dados fictícios desses cadastros.

Os quatro perfis são criados como usuários de teste pelo comando `python manage.py criar_usuarios_iniciais`, a partir das variáveis `USUARIO_*` do ambiente. Executar de novo não redefine a senha de um usuário que já existe.

O controle de acesso está no backend. Ocultar um item de menu não é a proteção.
