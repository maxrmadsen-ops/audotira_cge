# Perfis e responsabilidade pelos processos

## Separação oficial

| Perfil | Papel |
|--------|--------|
| **ADMINISTRADOR** | Governança e administração da plataforma. |
| **AUDITOR** | Visão transversal, supervisão e distribuição dos processos. |
| **ANALISTA** | Responsabilidade operacional pelos processos atribuídos, incluindo análise, validação, diligências e elaboração do parecer. |

Regra principal:

> Administrador e Auditor possuem visão transversal dos processos. O Analista possui visão operacional restrita aos processos sob sua responsabilidade.

Isso vale para listas, URLs, APIs, Painel 360° (KPIs, gráficos, Central de Atenção, filtros e contadores de menu), documentos, achados, pré-análises, diligências e pareceres.

## Usuários de homologação

| Username | Perfil | Finalidade |
|----------|--------|------------|
| `adm_cedro` | Administrador | Homologação do perfil administrador |
| `aud_ipe` | Auditor | Homologação do perfil auditor |
| `ana_araucaria` | Analista | Homologação do perfil analista |

Há senha inicial de homologação definida exclusivamente por `SENHA_HOMOLOGACAO` no ambiente. Troque antes de produção. A senha não está no código, migration, fixture, documentação versionada nem logs.

```bash
python manage.py criar_usuarios_homologacao
python manage.py criar_usuarios_homologacao --atualizar-senha
```

## Matriz de permissões

| Funcionalidade | Admin | Auditor | Analista |
|----------------|-------|---------|----------|
| Ver todos os processos | SIM | SIM | NÃO |
| Ver próprios processos | SIM | SIM | SIM |
| Criar usuário | SIM | NÃO | NÃO |
| Administrar usuários | SIM | NÃO | NÃO |
| Criar/editar regras | SIM | NÃO* | NÃO |
| Distribuir processos | SIM | SIM | NÃO |
| Redistribuir processos | SIM | SIM | NÃO |
| Anexar documentos | SIM | SIM | SIM** |
| Validar extrações | SIM | SIM | SIM** |
| Corrigir dados da prestação | SIM | SIM | SIM** |
| Solicitar diligência | SIM | SIM | SIM** |
| Elaborar parecer | SIM | SIM | SIM** |
| Administração | SIM | NÃO | NÃO |
| Saúde do sistema | SIM | NÃO | NÃO |
| Painel 360° (agregações) | todos | todos | só atribuídos |

\* Edição de catálogo de regras permanece administrativa. Execução de análise permanece operacional.  
\*\* Somente em processos atribuídos ao analista.

## Responsável pelo processo

Cada prestação pode ter `analista_responsavel`. Atribuição e redistribuição (Admin e Auditor) geram histórico append-only e eventos de auditoria com processo, analista anterior, novo analista, usuário responsável, data/hora e justificativa.

O Analista não atribui nem redistribui.

## Diligências

Interface vinculada ao processo: nova diligência, motivo, descrição, documentos, prazo, situação, registro de resposta recebida, encerramento e histórico. O sistema não inventa resposta do beneficiário.

Admin/Auditor visualizam diligências de todos os processos. Analista somente dos seus.

## Parecer final

Tela com três áreas separadas:

1. **Sugestão da IA** — somente apoio; preservada exatamente;
2. **Texto do analista** — editável;
3. **Versão final** — consolidada pelo analista.

O analista pode aproveitar integral/parcialmente, editar, ignorar ou escrever próprio texto. Histórico e versões são preservados. A sugestão nunca é apresentada como decisão administrativa.

## Perfil legado Consulta

O valor `CONSULTA` permanece no enum do banco para registros históricos e trilha de auditoria.

**Nesta fase:**
- não é atribuível na interface de usuários;
- não é criado por `criar_usuarios_iniciais` nem por homologação;
- mantém leitura transversal somente-leitura por dependência técnica de testes e de possíveis usuários históricos já existentes;
- não executa análise, não distribui processos e não administra.

**Pendência para decisão:** remoção completa da visão transversal do valor `CONSULTA` (deixando apenas os três perfis operacionais com qualquer acesso a processos). Não improvisar essa remoção sem autorização explícita, pois impacta a suíte e eventuais usuários legados.

## Painel 360° por perfil

| Perfil | Escopo das agregações |
|--------|------------------------|
| Administrador | Todos os processos |
| Auditor | Todos os processos |
| Analista | Exclusivamente processos com `analista_responsavel` = usuário autenticado |
