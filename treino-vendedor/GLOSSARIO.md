# Glossário do Treino de vendas

## O Treino

| Termo | Significado |
|---|---|
| Treino de vendas | O vendedor humano atende um cliente simulado pelo GPT e, no fim, recebe uma nota pela régua C12. Serve para desenvolver o vendedor, não para cobrar. |
| Modo treino | Com coach: depois de cada troca, o coach dá uma dica curta (se estiver ligado). |
| Modo prova | Sem dicas e sem coach. É o que conta para o nível da trilha. |
| Coach (IA) | Voz que comenta o que o vendedor poderia fazer melhor naquela troca. O botão "Coach IA" liga e desliga, antes de iniciar ou no meio do treino. Desligado = o líder coach acompanha no lugar da IA. Na prova, fica sempre desligado. |
| Trilha de treinamento | 9 competências (abertura, diagnóstico, Challenger, objeções, portfólio, suporte que vira oportunidade, fechamento e promessas, saúde da conta, disciplina de margem), cada uma com cenários e níveis Bronze, Prata e Ouro. As competências vêm dos 15 prompts de análise de ligações. |
| Nível (Bronze, Prata, Ouro) | Por competência, só com provas: nota geral e nota da dimensão principal ≥ 6 (fácil), ≥ 7 (médio) ou ≥ 8 (difícil, 2 provas, uma na frente ativa). |
| Frente receptiva / ativa | Receptiva: o cliente chama. Ativa: o vendedor chama o cliente da carteira, com o motivo do cadastro na tela. |
| Calculadora da alçada | Painel com as regras do mundo simulado (preço, volume, gerente, estoque). "Avaliar condição" mostra o que seria aprovado; "Registrar proposta" grava no treino sem mexer no estoque. |
| Minha evolução / gestor | Média, evolução e ponto a desenvolver por vendedor, em ordem alfabética, sem ranking. Mostra também a média com coach IA ligado, desligado, trocado no meio e em prova. |
| Piloto do Treino | 3 a 5 vendedores e 1 gestor no Q4/2026, com pelo menos 4 treinos por vendedor, antes de a nota "valer". |
| Calibração da nota | 2 a 3 gestores avaliam as mesmas ~20 conversas sem ver a nota da IA. Meta: a IA até 1,5 ponto da média dos gestores em ≥ 80% das dimensões. |

## O cliente simulado

| Termo | Significado |
|---|---|
| Persona | O cliente interpretado pelo GPT: contato, cargo, abertura, segredos, objeções, condição de aceite, desafio do cenário, janela de adicional e as competências que o cenário treina. São 30. |
| Segredo | Informação que o cliente só revela se o vendedor perguntar bem. O sistema conta quantos foram descobertos. |
| Condição de aceite | O que precisa acontecer para o cliente aceitar. |
| Dificuldade | Fácil, médio ou difícil: quanto o cliente colabora. |

## A nota

| Termo | Significado |
|---|---|
| Nota geral | Média ponderada (0 a 10) das dimensões que se aplicam à conversa. Pesos: diagnóstico 2, Challenger 2, objeções 2, oportunidades 1,5, disciplina de margem 1,5, fechamento 1,5, abertura 1, qualificação 1, promessas 1, sinais da conta 1, tom 1, adicionais 0,5. Promessas, sinais da conta e adicionais só entram quando houve promessa, sinal ou janela. |
| Abertura (AB1–AB5) | P9. AB1 contextualizada · AB2 relacional · AB3 genérica · AB4 reativa · AB5 de proteção. Também: usou o nome, mostrou que viu a conta, primeira pergunta de diagnóstico ou de confirmação. No contato ativo, abrir sem pergunta vale no máximo 4 (regra do sistema). |
| Comportamentos B1–B10 | P1. Ex.: B1 diagnóstico antes do produto, B3 usou o histórico, B6 urgência com fato verificável, B10 perguntou sobre concorrente ou frota própria. Aparecem no diagnóstico. |
| Challenger (CH1–CH7) | P5. Ensinar com dado concreto. Sem dado, a nota fica limitada a 4 (regra do time, 24/09/2026). |
| Objeções (OB1–OB7) e respostas (R1–R6) | P8. R1 validou e explorou · R2 usou dado do cliente · R3 urgência · R4 aliado · R5 capitulou · R6 argumentou sem ouvir. |
| Oportunidades perdidas (OP1–OP8) | P6. Ex.: OP1 suporte sem pergunta comercial, OP2 dor sem produto, OP4 indicação não pedida, OP7 churn ignorado, OP8 escalada desnecessária. Cada uma vem com o que faltou e o que deveria ter dito. |
| Promessas (PM1–PM6) | P10. Tudo o que o vendedor disse que vai fazer, com prazo e risco. Promessa sem prazo derruba a nota. |
| Sinais da conta (IC1–IC7, EV_R1–EV_R5) | P11 e P15. Concorrente, exclusividade, frota própria, expansão, risco de churn, troca de gestor… e se o vendedor explorou. |
| Fechamento (FC1–FC5) | P9. FC1 compromisso duplo (vendedor, cliente e prazo) é o melhor. |
| Disciplina de margem | Calculada pelo sistema: desconto sem contrapartida, limite revelado e preço que não bate com a tabela. |
| Escuta (TL1–TL3) | P12, calculada pelo sistema: % das palavras que foram do vendedor e quantas perguntas ele fez. TL1 vendedor domina (> 60%) · TL2 equilibrado · TL3 cliente domina (< 40%). Aparece no resultado, sem peso na nota. |
| Âncora | Trecho literal da fala do vendedor que sustenta a nota. O sistema confere se ele realmente escreveu aquilo. |
