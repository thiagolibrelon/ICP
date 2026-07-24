# Modelo de Dados para Power BI (Fase 5)

**Responsável:** Bruno Salgado
**Limitação importante:** não é possível gerar um arquivo `.pbix` binário por código — o Power BI Desktop precisa ser aberto manualmente para montar o relatório. Este documento é o roteiro exato para isso, com o modelo já pronto do lado dos dados (`master_classificada/MASTER_CLASSIFICADA.csv`).

## 1. Fonte única

`MASTER_CLASSIFICADA.csv` já é a tabela final, 1 linha por `CODIGO_CLIENTE`, 85.941 linhas, 43 colunas — os merges das Fases 1-4 já foram feitos em Python (pandas), não precisam ser refeitos em Power Query. Importar direto como tabela única (`Obter Dados > Texto/CSV`, delimitador `;`, codificação UTF-8).

Não é necessário montar um esquema estrela com várias tabelas — a granularidade "1 linha por cliente" já resolve isso para os relatórios de ICP/Score/Tier. Se no futuro for necessário um relatório de detalhe transacional (ex.: reserva a reserva), aí sim os `processado/agg_*.csv` viram tabelas satélites relacionadas por `CODIGO_CLIENTE`.

## 2. Tipos de coluna a conferir na importação

| Coluna | Tipo Power BI |
|---|---|
| `CODIGO_CLIENTE` | Texto (não número — evita notação científica, mesmo problema já visto no CNPJ) |
| `DATA_ULTIMO_CONTRATO`, `ULTIMA_ATIVIDADE` | Data |
| `SCORE_*`, `RECENCIA_DIAS`, `FREQUENCIA_ANUAL`, `VOLUME_*` | Número decimal |
| `TIER`, `CLUSTER_PRINCIPAL`, `ICP_ATRIBUIDO`, `CONFIANCA` | Texto (categórico) |

## 3. Medidas DAX sugeridas

```
Clientes Tier A = CALCULATE(COUNTROWS(MASTER_CLASSIFICADA), MASTER_CLASSIFICADA[TIER]="A")
Volume Total 24M = SUM(MASTER_CLASSIFICADA[VOLUME_24M_FINAL])
Score ICP Médio = AVERAGE(MASTER_CLASSIFICADA[SCORE_ICP])
% Base em Risco = DIVIDE(CALCULATE(COUNTROWS(MASTER_CLASSIFICADA), MASTER_CLASSIFICADA[CLUSTER_PRINCIPAL]="Em risco"), COUNTROWS(MASTER_CLASSIFICADA))
Volume por Cluster = SUM(MASTER_CLASSIFICADA[VOLUME_24M_FINAL]) -- usar com CLUSTER_PRINCIPAL no eixo
```

## 4. Páginas de relatório recomendadas

1. **Visão geral** — cards (clientes por Tier, Score ICP médio, % em risco) + mapa por `ESTADO`/`REGIAO`.
2. **ICPs** — tabela `TABELA 1` (ver `saidas/tabela1_resumo_icps.csv`) + gráfico de barras por `ICP_ATRIBUIDO`.
3. **Clusters** — treemap de `CLUSTER_PRINCIPAL` por `VOLUME_24M_FINAL`, tabela de ação por segmento (`saidas/tabela3_acoes_por_segmento.csv`).
4. **Base classificada (detalhe)** — tabela navegável ligada a `saidas/tabela2_base_classificada.csv`, com filtros por Tier/Cluster/Região.
5. **Top oportunidades** — `saidas/tabela4_top_oportunidades.csv`.

## 5. Performance

85.941 linhas é tranquilo para o Power BI/VertiPaq (nem perto do limite prático) — não há necessidade de chunking nesta fase, ao contrário do que a auditoria original havia previsto como risco para a exportação bruta em CSV.

## 6. Pendência

Alguém com Power BI Desktop precisa efetivamente abrir o `.csv` e montar o `.pbix` seguindo este roteiro — nenhuma IA consegue gerar o binário do Power BI diretamente.
