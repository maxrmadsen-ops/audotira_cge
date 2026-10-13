# Administração

Nesta onda, o perfil `ADMINISTRADOR` acessa:

- Gestão de usuários, em `/administracao/usuarios/`
- Saúde do Sistema, em `/saude/`
- Registros de auditoria, em `/auditoria/registros/`
- Administração técnica do Django, em `/admin/`

Os três perfis operacionais (Administrador, Auditor e Analista) são descritos em `PERFIS_E_RESPONSABILIDADE.md`.

Os usuários de desenvolvimento continuam sendo criados por `python manage.py criar_usuarios_iniciais`, a partir das variáveis `USUARIO_*` do ambiente. Executar de novo não redefine a senha de um usuário que já existe.

Os usuários de homologação (`adm_cedro`, `aud_ipe`, `ana_araucaria`) são criados por `python manage.py criar_usuarios_homologacao`, com senha exclusiva de `SENHA_HOMOLOGACAO`. A senha não entra no Git.

O controle de acesso está no backend. Ocultar um item de menu não é a proteção.
