# Pedido de orçamento — uso do llm-gate no 4º trimestre de 2026

| | |
|---|---|
| Para | [gestor] |
| De | [responsável] |
| Data | 07/10/2026 |
| Pedido | **US$ 200** de uso do llm-gate (GPT 5.4 mini) até 19/12/2026 |

## 1. Para que serve

Todo o projeto já está construído e roda na máquina da empresa. O que falta é **usar o GPT de verdade** para gerar as
evidências da decisão de 19/12: rodar os testes da Fernanda (receptiva e ativa), o piloto do Treino e a referência do
time (C12). Sem esse orçamento, o MVP fica parado no ponto em que está.

## 2. Para onde vai cada dólar

As estimativas abaixo vêm do próprio Laboratório (~US$ 0,06 por conversa de teste, incluindo a nota C12). A primeira
rodada real calibra os números; se o custo real passar 30% da estimativa, eu paro e reporto antes de seguir.

| Item | Volume | Estimativa |
|---|---|---|
| Suíte completa de testes × 3 rodadas (linha de base, ajuste, regressão final) | 390 conversas por rodada: completa 192, críticos 30, conversas longas 12, red team 36, negociação 36, frente ativa 84 | **US$ 78** |
| Teste das duas aberturas (antes da linha de base) | 120 conversas | US$ 8 |
| Comparação de modelos da Fernanda (5.4 mini × outro modelo do gate) | ~80 conversas por modelo; modelo maior custa mais | US$ 25 |
| Referência do time: reclassificar 12 meses de ligações pelo C12 com o 5.4 mini | ~10 mil receptivas + amostra das ativas | US$ 50 |
| Testes manuais do roteiro (blocos A a K) | ~150 conversas | US$ 9 |
| Piloto do Treino | 3 a 5 vendedores × 4 a 6 treinos | US$ 3 |
| Rodadas de ajuste e reexecuções | — | US$ 10 |
| **Subtotal** | | **US$ 183** |
| Reserva (~10%) | | US$ 17 |
| **Total** | | **US$ 200** |

## 3. O que volta para a empresa

- **A decisão de 19/12 com números**, não opinião: a Fernanda erra preço, desconto ou margem? Vende como o time?
  Respeita a alçada e o gerente? Resiste a ataques? Funciona chamando o cliente (frente ativa)?
- **A referência do time em 12 meses na mesma régua** (C12 com o mesmo modelo), que serve além do projeto: mostra
  onde o time perde venda (ex.: em setembro, Challenger com dado em só 22,9% das receptivas de venda).
- **O Treino calibrado** com o grupo piloto: uma ferramenta de desenvolvimento para os vendedores.
- **O custo real por conversa**, que é a base do caso de negócio do piloto de 2027.

Para comparar: as ~1.400 conversas de teste do trimestre, se feitas por pessoas, levariam semanas de trabalho do time.
No Laboratório, cada rodada completa leva cerca de 2 a 3 horas, sem ninguém digitando.

## 4. Como o gasto é controlado

- **Antes de cada rodada**, a tela mostra o custo e o tempo estimados; nada roda sem essa conferência.
- **Depois de cada rodada**, o relatório mostra o custo real (por conversa e total), lido do próprio llm-gate.
- **Teto:** US$ 200 no trimestre. Acompanhamento no status quinzenal (gasto acumulado × previsto).
- **Regra de parada:** custo real 30% acima do estimado → paro, reporto e recalculo antes de continuar.
- Só dados fictícios nos testes; a reclassificação das ligações gera apenas números agregados (sem trechos nem nomes).

## 5. O que preciso nesta reunião

1. Aprovação dos US$ 200 (ou do valor possível; com menos, corto primeiro a comparação de modelos e reduzo as rodadas
   de 3 para 2).
2. Confirmação de onde a cota é lançada no llm-gate (centro de custo / chave do projeto).
