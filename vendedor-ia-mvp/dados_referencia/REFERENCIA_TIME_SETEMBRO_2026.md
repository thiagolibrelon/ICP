# Referência do time: C12 das ligações de setembro/2026

> Roadmap **S1-03** (parte C12). Números **agregados**, sem trechos, nomes ou identificadores de ligação.
> Fonte: saída consolidada do `classificar_ligacoes_diario.py` (8.008 ligações, 01 a 30/09/2026), resumida por
> `scripts/resumo_c12.py` (que roda na máquina do time). Detalhe completo em `referencia_time_c12_setembro_2026.json`.
> A parte do CRM (conversão, ticket, desconto médio, tempo de resposta) ainda está pendente.

## 1. O recorte que vale para comparar com a Fernanda

| | |
|---|---|
| Ligações no mês | 8.008 (7.153 ativas, **855 receptivas**) |
| Receptivas classificadas pelo C12 | 762 (as demais eram curtas demais para classificar) |
| Receptivas de **venda** (nova venda, renovação, upsell, misto, retenção) | 324 no mês |
| **Referência recomendada** | **168 receptivas de venda de 15 a 30/09**, classificadas pelo **gpt-5.4-mini** |

**Por que só a segunda quinzena:** o modelo do classificador mudou em 15/09 (gpt-4o-mini → gpt-5.4-mini) e a régua
mudou junto. Nas mesmas receptivas de venda, a "tentativa comercial" caiu de 92,8% para 35,6% e as ligações com
problema subiram de 26,6% para 55,7%. O time não mudou tanto em duas semanas; o classificador, sim. A segunda quinzena
usa o mesmo modelo da Fernanda, então é a comparação justa.

## 2. Números de referência (receptivas de venda, gpt-5.4-mini)

| Indicador | Time | O que significa |
|---|---|---|
| Fechou na própria ligação | **12,7%** (9,0% venda nova + 3,6% renovação) | 86,7% terminaram em "interessou, não fechou" |
| Tentativa comercial | **41,0%** | O vendedor tentou avançar a venda (proposta, próximo passo) |
| Challenger **com dado** | **22,9%** | Ensinou algo com número ou regra real; sem dado não conta (regra de 24/09) |
| Qualidade dos Challengers | 89,7% alta · 10,3% média | Quando acontece, costuma ser bom |
| Conectou à situação do cliente | 26,2% | |
| Cliente reagiu ao ensino | 23,8% | |
| Ligação com problema | 49,4% | Metade das receptivas de venda carrega um problema junto |
| Problema resolvido na ligação | 13,3% sim · 69,9% parcial · 16,9% não | |

**Tipos de Challenger do time** (% dos Challengers): antecipação de problema 66,7% · urgência por regra real 51,3% ·
custo oculto 25,6% · necessidade não declarada 7,7% · concorrente superado 5,1% · dor conectada a produto 5,1% ·
**ROI calculado 2,6%**.

**Problemas mais frequentes** (% das ligações): **crédito/cadastro PJ 20,8%** · acesso/sistema 9,5% ·
faturamento/cobrança 8,9% · disponibilidade 7,7% · reserva/sistema 7,1% · preço/competitividade 2,4%.

## 3. O que isso muda no projeto

1. **A meta "nota C12 ≥ média do time" precisa virar indicadores.** A saída do C12 não tem uma nota única de 0 a 10;
   tem indicadores (Challenger com dado, tentativa comercial, desfecho, problemas). A comparação justa é: exportar as
   conversas da Fernanda (Simulador › Exportar p/ classificador), **rodar o mesmo classificador com o gpt-5.4-mini** e
   comparar estes mesmos indicadores. Proposta de metas para a Fernanda (modo B), a validar com o gestor:
   - Challenger com dado nas conversas de venda: **≥ 23%** (o time) e meta de **≥ 50%**, porque ela tem as
     comparações calculadas pelo sistema;
   - tentativa comercial: **≥ 41%** (o time);
   - conectou à situação do cliente: **≥ 26%** (o time).
2. **Onde a Fernanda pode se diferenciar:** o time quase não usa **ROI calculado** (2,6%) nem **dor conectada a
   produto** (5,1%). As comparações da Fernanda (diária × mensal, elétrico × combustão) e os adicionais ligados à
   situação do cliente são exatamente isso.
3. **A régua também precisa ser congelada (S1-02):** o modelo do classificador entra na suíte congelada. Trocar o
   modelo no meio do trimestre invalida as comparações, como aconteceu em setembro.
4. **Lacuna do simulador:** crédito/cadastro PJ é o problema nº 1 nas receptivas de venda (20,8%), e o mundo simulado
   não tem crédito. Candidato a cenário novo (ex.: cliente com limite de crédito comprometido) depois da linha de base.

## 4. Limitações

- **Sem identificação do vendedor:** não dá para calcular melhor quarto, média e pior quarto do time; só a média.
- **Amostra pequena:** 168 ligações na referência. Suficiente para a ordem de grandeza; outubro aumenta a base.
- **Canal diferente:** o time fala por telefone; a Fernanda escreve no WhatsApp.
- **"Fechou na ligação"** não é a conversão do funil (vendas que fecham depois não aparecem). A conversão real vem do CRM.
