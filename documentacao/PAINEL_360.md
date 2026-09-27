# Painel 360°

O Painel observa e prioriza. Os menus operam. O FinOps, em menu próprio, gere consumo e custo da inteligência artificial.

A home deixa de ser uma grade de cartões soltos. A Central analítica segue a jornada da auditoria:

1. Visão 360°
2. Processos
3. Documentos
4. Normas & Referenciais
5. Regras & Verificações
6. Evidências
7. Achados
8. Pré-Análise
9. Revisão Humana
10. IA × Técnico
11. Operação & IA

A ordem não é alfabética e não segue os aplicativos Django.

## O que cada superfície faz

| Superfície | Pergunta | Onde |
|---|---|---|
| Painel | O que está acontecendo? | `/` e `/painel/…` |
| Menus | Quero investigar, validar ou atuar | Prestações, Documentos, Normas, Regras, Inteligência Artificial, Achados, Pré-Análises, Avaliação |
| FinOps | Quanto a IA consumiu e quanto custou? | `/finops/` |
| Administração | Quem existe e o que a trilha registrou? | `/administracao/` |
| Saúde | Os componentes locais respondem? | `/saude/` |

O menu lateral não ganha uma entrada por aba. `/modulos/finops/` redireciona para `/finops/`. As URLs anteriores de prestação, documento, norma, regra, achado, pré-análise, avaliação e laboratório permanecem.

## Filtros

A barra é a mesma em todas as abas e no FinOps. Cada aba oferece só as dimensões que o modelo daquela aba possui: período, prestação, situação, concedente, beneficiário, tipo de instrumento, responsável, criticidade, categoria, natureza, tipo documental, regra, categoria da regra, tipo de execução, agente, modelo, provedor e origem (`demonstracao` ou `operacional`).

Filtro ativo aparece como etiqueta e pode ser removido. “Limpar filtros” volta à aba sem parâmetros.

Na Visão 360°, o período e a situação recortam as prestações. Documentos, regras, evidências, achados e pré-análises entram se pertencem a essas prestações. Nas demais abas, o filtro incide no próprio objeto. A situação muda de significado conforme a aba: situação da prestação, status do documento, vigência da norma, status do achado ou status da pré-análise. O pipeline da Visão 360° limpa a situação ao abrir outra aba, para que o status da prestação não seja lido como status de documento.

Registros de demonstração continuam visíveis e identificados. O filtro de origem separa demonstração e operação. Não se cria Ground Truth nem avaliação em `DEMO-2024-001` para preencher o painel.

## Visão 360°

Responde, com os dados existentes: quanto trabalho há, em que situação cadastrada está, o que pede atenção, o que já foi produzido no fluxo e como a comparação IA × técnico se apresenta quando há avaliação.

Blocos:

- indicadores da carteira, inclusive materialidade somente quando há valor informado;
- processos por situação, com atalho para a aba Processos;
- Central de Atenção, no máximo doze ocorrências reais, ordenadas pela criticidade já gravada e, em seguida, pela data;
- pipeline Documentos → Regras executadas → Evidências → Achados → Pré-análises → Revisões humanas;
- achados por criticidade e por natureza;
- evolução somente quando uma série tem pelo menos dois meses distintos.

Não há SLA, score de prioridade nem nota geral da IA.

## Central de Atenção

Cada item tem tipo, objeto, data, prestação, criticidade existente quando houver, e link para a tela operacional. Entram, quando existem no recorte: achado de criticidade alta ou crítica, achado em revisão, documento aguardando validação ou com erro, execução não verificável ou não localizada, pré-análise aguardando revisão, correspondência pendente, falso negativo crítico, falha controlada de IA e avaliação aguardando ação.

A ordem usa a criticidade já cadastrada. Não há nota calculada.

## Gráficos

Os gráficos são barras em HTML e CSS, com título, descrição, valor e estado vazio. Não há biblioteca externa nem CDN. Baldes com quantidade zero não desenham barra; a contagem zero permanece no indicador. Ausência, denominador zero e materialidade nula aparecem como “Não disponível”. Série com menos de dois meses aparece como “Sem dados históricos suficientes.”

## Permissões

Os quatro perfis leem o Painel e o FinOps. O drill-down abre a tela operacional correspondente e herda a permissão dela. Consulta não administra, não abre a saúde, o laboratório nem o consumo de IA. O administrador continua sem congelar Ground Truth nem avaliação.

A renderização do Painel não gera evento de auditoria.

## Consultas

As agregações ficam em `aplicacao/painel/consultas/`. Os templates só recebem indicadores, séries e linhas já calculados. Não há data warehouse nem cache desta onda. A definição de cada número está em [Indicadores da Onda 9](INDICADORES_ONDA9.md).
