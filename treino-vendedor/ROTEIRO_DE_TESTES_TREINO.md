# Roteiro de Testes — Treino de vendas

> **Para quem é:** quem vai testar o Treino **sem conhecê-lo**. Siga na ordem. Não precisa saber programar.
> **Tempo estimado:** meio dia por rodada. **Versão:** 1.0 — 06/10/2026.
> Os blocos T01–T04, C01 e K10 vieram do roteiro da Fernanda (antigos G01–G04, I02 e K10).

**Tudo é fictício**: empresas, CNPJs, preços e estoque. **Nunca digite dados reais.**

## Bloco A — Antes de começar

| ID | Teste | Deve acontecer |
|---|---|---|
| A01 | Rode `python iniciar.py` (pasta `treino-vendedor`) | Diagnóstico da conexão OK e o navegador abre em `http://127.0.0.1:8001` |
| A02 | Olhe o topo da tela | "GPT conectado" em verde |
| A03 | Abra a lista de clientes | 30 clientes, de "Alpha Obras" a "Cassini Educação" |

Se A01 ou A02 falharem, **pare** e avise o responsável.

---

## Bloco T — A nota é justa?

O objetivo é verificar se **a nota é justa**. Para isso, você faz o mesmo cenário **duas vezes**: uma como **bom
vendedor** e outra como **mau vendedor**.

### Preparação
Informe seu nome → cliente **Alpha Obras — Rogério** → dificuldade **Médio** → modo indicado → **Iniciar**.

### T01 · Bom vendedor (modo treino, coach ligado)
Siga este comportamento (adapte as palavras):
1. Pergunte como usam os carros e **quantos dias por mês**.
2. Pergunte **quem decide** e **quando**.
3. Use a **Calculadora**: Onix, Curitiba, Mensal, Qtd 3, 12 meses → **Avaliar condição**. Mostre ao cliente a diferença
   contra a diária (22 dias ≈ R$ 10.494,00/mês × mensal R$ 8.070,00/mês).
4. Trate a objeção do prazo com calma (ex.: explicar a regra e as opções).
5. Ofereça **proteção total**, ligada ao uso em obra.
6. Combine o próximo passo com data: `te mando a proposta hoje e você me confirma até sexta com o Marcos?`
7. Clique em **Encerrar e ver nota**.

- **Deve acontecer:** nota geral **alta (≥ 7)**; justificativas coerentes; trechos citados que você realmente escreveu;
  "Disciplina de margem" = 10.
- **No modo treino:** aparecem dicas do Coach depois das suas respostas.

### T02 · Mau vendedor (modo prova, sem dicas)
1. Logo na primeira resposta, fale o preço sem perguntar nada.
2. Dê **5% de desconto sem pedir nada em troca**: na Calculadora, Qtd 3, 12 meses, Desconto 5 → **Avaliar condição**
   (deve vir "Gerente negou"); depois Desconto 2 → **Registrar proposta**.
3. Escreva: `o máximo que eu consigo é 6%`.
4. Encerre sem combinar próximo passo.

- **Deve acontecer:** nota geral **baixa (≤ 5)**; **Disciplina de margem baixa**, citando o desconto sem contrapartida e o
  limite revelado; Qualificação e Fechamento baixos; nenhuma dica do coach (modo prova).

### T03 · Outras personas (escolha 3)
Repita como **bom vendedor** com: **Épsilon** (o certo é recomendar a diária), **Teta** (o certo é dizer que o Dolphin não
compensa) e **Eta Seguros, dificuldade Difícil** (o cliente vai tentar arrancar o seu limite).

- **Deve acontecer:** nas personas de honestidade, a nota de Challenger premia quem disse a verdade com números.

### T04 · Evolução
Clique em **Minha evolução / gestor**.
- **Deve acontecer:** seu nome aparece em ordem alfabética, com média, evolução e "ponto a desenvolver". **Sem ranking.**

### Registro de cada treino
Para cada treino, anote na planilha: nota geral, nota de cada dimensão e **"A nota foi justa?"** (Sim / Parcial / Não +
por quê). Esse campo é o mais importante do bloco.

### T05 · Nota completa
Em qualquer treino encerrado, abra **Ver justificativa completa**.
- **Deve acontecer:** aparecem **Abertura** (tipo AB, nome, conta, primeira pergunta), **Oportunidades aproveitadas** (com
  as oportunidades perdidas e o que deveria ter dito), **Promessas** (se você prometeu algo, com prazo e risco), **Sinais
  da conta** (se o cliente deu algum sinal) e a linha **Escuta** (% das palavras que foram suas e quantas perguntas).
- Faça um treino com **Lyra Saúde** (cobrança em dobro) e prometa "vou verificar" **sem prazo**: a nota de Promessas
  deve cair e citar a falta de prazo.
- Faça um treino com **Nu Farmacêutica** (multa) e encerre depois de resolver a multa **sem nenhuma pergunta
  comercial**: Oportunidades deve listar OP1 ou OP2.

---

## Bloco L — Coach e trilha

| ID | Teste | Como fazer | Deve acontecer |
|---|---|---|---|
| L01 | Coach desligado | Antes de iniciar, clique **Coach IA** até ficar "desligado"; faça 2 respostas | Nenhuma dica; o cadastro mostra "(coach desligado)" |
| L02 | Trocar no meio | Num treino com coach, desligue depois da 1ª resposta | Dicas param; no resultado: "trocado no meio" e 1 troca |
| L03 | Prova | Escolha **Modo prova** | O botão fica "desligado na prova" e não clica |
| L04 | Evolução por coach | Abra **Minha evolução / gestor** | Médias separadas por coach ligado, desligado, trocado e prova |
| L05 | Trilha | Clique **Trilha** com o seu nome | 9 competências, regras dos níveis e cenários clicáveis |
| L06 | Nível | Faça uma prova média bem feita num cenário de Challenger (ex.: Rô Engenharia) | A competência sobe para Prata se a nota geral e a de Challenger forem ≥ 7 |

---

## Bloco K — Frente ativa

| ID | Teste | Como fazer | Deve acontecer |
|---|---|---|---|
| K10 | Treino ativo | Escolha **Ativa (você chama o cliente)** | O motivo aparece no cadastro; você escreve primeiro; a nota avalia sua abertura e se respeitou o tempo do cliente |

---

## Bloco C — Calibração (com o responsável)

### C01 · Calibração da nota
2 a 3 gestores leem as **mesmas ~20 conversas de treino** (exportadas) e dão nota de 0 a 10 em cada dimensão, **sem ver a
nota da IA**. O responsável compara.
- **Resultado esperado:** em ≥ 80% das dimensões, a nota da IA fica a até 1,5 ponto da média dos gestores.

---

## Critérios de aprovação

| Critério | Para passar |
|---|---|
| T01 × T02 | Diferença clara de nota (bom ≥ 7; mau ≤ 5) e "nota justa" = Sim em ≥ 80% |
| Coach (L01–L03) | 100% dos casos como esperado |
| Nota completa (T05) | Promessa sem prazo e suporte sem pergunta comercial aparecem na nota |
