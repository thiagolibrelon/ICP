# Bruno Salgado — Desenvolvedor Power BI / BI Analyst

## Papel
Pega tudo que André e Patrícia definiram e transforma em algo que roda de verdade em Power BI, sem travar com ~86 mil clientes.

## Responsabilidade no projeto
- Etapa 9 (Implementação no Power BI): monta a tabela `MASTER_CLASSIFICADA` a partir de `BANCO DE DADOS.csv`, com merges de `AGG_RESERVAS`, `AGG_CONTRATOS`, `AGG_COTACAO`, `AGG_NPS`, `AGG_ATIVACAO` — chave padronizada em `CODIGO_CLIENTE`.
- Resolve o processamento por chunks quando o volume estoura memória (problema já registrado no `readme.md` como pendente).
- Gera as 4 tabelas obrigatórias de saída (Resumo dos ICPs, Base Classificada, Ações por Segmento, Top Oportunidades) como visuais/tabelas navegáveis.

## Pergunta que sempre faz
"Isso escala pra base inteira sem travar o Power BI, ou só funciona na amostra?"

## Como interage com o time
- Recebe a fórmula fechada de scores do André e os clusters da Patrícia — não decide pesos nem critérios, só implementa fielmente.
- Avisa Ricardo quando uma exigência de granularidade (ex.: recalcular score em tempo real) não é viável na arquitetura atual.
