# CGE — Análise Inteligente de Prestação de Contas

Fundação da plataforma de análise assistida de prestações de contas da Controladoria-Geral do Estado de Santa Catarina.

A inteligência artificial não aprova nem reprova uma prestação de contas. A decisão administrativa permanece com o auditor.

O caso `2022TR000929` será apenas o primeiro caso de teste, em onda posterior. Ele não está fixado nesta fundação e nenhum resultado foi inventado para ele.

## Onda atual

Onda 7 — pré-análise técnica assistida por IA, sobre as evidências e os achados da Onda 6. A integração com provedores nasce desligada. A IA redige fatos já apurados; o auditor revisa, congela e decide.

## Execução

A aplicação roda em Linux, dentro dos containers. O Python do host não é requisito.

```bash
bash instala.sh
```

No Windows, com Docker Desktop e Git Bash:

```bash
"C:\Program Files\Git\bin\bash.exe" instala.sh
```

Acesse `http://127.0.0.1:8080/`.

As credenciais efetivas ficam somente no `.env`, que não entra no Git. O `.env.example` traz apenas placeholders.

## Perfis

| Usuário (padrão de desenvolvimento) | Perfil |
|---|---|
| admin | ADMINISTRADOR |
| auditor | AUDITOR |
| analista | ANALISTA |
| consulta | CONSULTA |

## Repositório

O remoto previsto é `https://github.com/maxrmadsen-ops/audotira_cge.git`. O nome `audotira_cge` deve ser preservado.

## Documentação

- [Arquitetura](documentacao/ARQUITETURA.md)
- [Instalação](documentacao/INSTALACAO.md)
- [Administração](documentacao/ADMINISTRACAO.md)
- [Usuário](documentacao/USUARIO.md)
- [Segurança](documentacao/SEGURANCA.md)
- [Testes](documentacao/TESTES.md)
- [Deploy](documentacao/DEPLOY.md)
- [Changelog](documentacao/CHANGELOG.md)
