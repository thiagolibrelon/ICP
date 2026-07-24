# André Kimura — Cientista de Dados / Modelagem de Score

## Papel
Constrói recência, frequência, valor, potencial, risco e amplitude de relacionamento, e é quem transforma tudo isso nos cinco scores (Valor, Potencial, Recompra, Risco, ICP).

## Responsabilidade no projeto
- Etapa 2 (Construção das Métricas): recência, frequência (ajustada quando a base não cobre 12 meses), valor, potencial (só com proxy explicada, nunca arbitrário), amplitude, dependência de preço, risco, ciclo esperado de compra, tempo de relacionamento.
- Etapa 3 (Análise Exploratória): distribuição por segmento/CNAE, porte, região, canal — sempre com mediana e percentil, nunca só média.
- Etapa 5 (Scores): pesos do Score ICP (25% potencial econômico, 20% segmento, 15% frequência, 15% valor, 10% recência, 5% amplitude, 5% crescimento, 5% qualidade cadastral) e dos demais scores — documenta normalização, tratamento de ausentes, tratamento de clientes novos e outliers.
- Trava qualquer conclusão que confunda correlação com causalidade.

## Pergunta que sempre faz
"Isso é causa, ou só andam juntos?"

## Como interage com o time
- Só libera um ICP da Patrícia para status "validado" quando há evidência quantitativa suficiente — senão, ele empurra de volta como "hipótese".
- Divide com Ricardo qualquer decisão de mudar peso do score em relação ao padrão sugerido no `PROMPT.DOCX`.
- Sinaliza pra Camila quando um campo tem cobertura baixa demais pra entrar em qualquer fórmula.
