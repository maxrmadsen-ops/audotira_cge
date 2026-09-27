# Piloto real

O primeiro processo da CGE/SC não entra com o deploy. Há dois portões.

## Checkpoint 10.1 — pré-deploy

Ambiente de notebook validado, release descrita, imagem nomeada e plano de Linux escrito. Parar e esperar autorização para implantar.

## Checkpoint 10.2 — pronto para dado real

Só depois do deploy autorizado, e só quando estiver comprovado:

- aplicação no ar;
- rede de acesso definida, com HTTPS se houver certificado, ou HTTP restrito à rede autorizada se não houver;
- login e perfis conferidos;
- banco e documentos em volume persistente;
- backup e restore documentados e um backup real já gerado;
- logs sem segredo;
- segredos só no `.env` do servidor;
- saúde e migrations conferidas;
- suíte e smoke do ambiente;
- rollback conhecido;
- `DEMO-2024-001` visível como demonstração, nunca como processo da CGE.

Sem isso, não carregar documento real.

## DEMO-2024-001

Não apagar. É o cenário de regressão. No piloto, a opção adotada até nova decisão é mantê-lo identificado como demonstração e separável pelo filtro “Somente operacionais”. Não misturar a contagem dele com processo real sem esse filtro explícito. Não movê-lo para outro banco nesta onda.

## Quando a carga for autorizada

1. Identificar o processo e gravar os metadados reais.
2. Receber os documentos no volume `cge_arquivos`, não na imagem e não no Git.
3. Classificar, extrair, aplicar normas e regras já existentes.
4. Gerar evidências e achados a partir dessa execução.
5. Produzir pré-análise e submetê-la à revisão humana.
6. Ground Truth, se houver, nasce depois e fora do prompt, do RAG, do motor, da evidência, do achado e da pré-análise. Não serve para ensinar a análise daquele mesmo processo.

Fonte excluída de teste cego continua fora do RAG, da evidência, do achado, da pré-análise e do contexto do modelo. O deploy não altera essa exclusão.

## PDF da pré-análise

Desejável para o piloto e dispensável para a homologação técnica. A saída oficial hoje é HTML. Um PDF novo mexe em exportação e em dependência de renderização. Fica para decisão posterior, sem implementação nesta onda.
