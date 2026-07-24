# Auditoria de Dados — Base de Clientes B2B (Localiza)

**Responsável:** Camila Duarte (Engenharia de Dados) — ver [`../personas/02-camila-engenharia-dados.md`](../personas/02-camila-engenharia-dados.md)
**Revisão de compliance:** Rafael Toledo — ver [`../personas/07-rafael-lgpd-compliance.md`](../personas/07-rafael-lgpd-compliance.md)
**Data da auditoria:** 2026-07-24
**Método:** leitura direta de todos os arquivos com parser de CSV real (respeitando aspas e delimitador `;`), não split ingênuo — ver seção 3 sobre por que isso importa.

---

## 1. Achado crítico — CNPJ corrompido em notação científica

**71,9% da base principal (61.820 de 85.941 clientes) tem o campo `CNPJ` salvo em notação científica** (ex.: `1,04239E+13` em vez do CNPJ completo de 14 dígitos).

- Isso é perda de precisão **irreversível**: um número em notação científica com 6 dígitos significativos não permite reconstruir os dígitos finais do CNPJ original.
- Impacto direto: **CNPJ não pode ser usado como chave de deduplicação, cruzamento com bases externas (ex. Receita Federal, CNAE oficial) ou identificação de Grupo Econômico por raiz de CNPJ** enquanto não for corrigido na fonte.
- `CODIGO_CLIENTE` (a chave interna) **não tem esse problema** — está íntegro e é único (85.941 valores únicos para 85.941 linhas, zero duplicados). Recomendação: usar `CODIGO_CLIENTE` como chave primária de tudo, nunca o CNPJ como está hoje.
- **Causa provável:** exportação de planilha (Excel) formatando a coluna como número em vez de texto antes de gerar o CSV.
- **Ação necessária antes de qualquer uso do CNPJ:** reexportar `BANCO DE DADOS` diretamente do sistema de origem com a coluna CNPJ forçada como texto, ou aceitar que o CNPJ dessa base é só um proxy de agrupamento aproximado, nunca identificador exato.

## 2. Achado crítico — `HISTORICO DE RESERVA.csv` está truncado, não é o histórico completo

O arquivo tem exatamente **150.000 linhas** (número redondo suspeito) e, ao checar o período coberto, o corte é abrupto:

| Mês | Linhas |
|---|---|
| 2025-01 | 23.877 |
| 2025-02 | 30.308 |
| 2025-03 | 32.371 |
| 2025-04 | 30.869 |
| 2025-05 | 32.526 |
| 2025-06 | **49** |

O arquivo para no meio do dia 1º de junho/2025 — não é o mês incompleto por estarmos "no meio do mês" (a base foi baixada em 2026), é uma **exportação cortada no limite de 150 mil linhas**. Isso significa:

- O nome do arquivo (`HISTORICO DE RESERVA`) promete histórico completo, mas na prática só existem ~5 meses de 2025.
- Qualquer métrica de **frequência, recência ou ciclo de compra baseada nessa tabela vai estar sistematicamente enviesada** para clientes que reservaram nesse período de 5 meses — clientes com atividade recente (2026) ou mais antiga (2024) ficam invisíveis nessa fonte.
- **Ação necessária:** reexportar sem limite de linhas, ou exportar em blocos por período (ex.: um CSV por trimestre) antes de calcular qualquer métrica de recência/frequência de reservas.

## 3. Achado técnico — campos com `;` dentro de aspas quebram parsers ingênuos

Cerca de **5,8% das linhas** (4.988 de 85.941) de `BANCO DE DADOS.csv` têm campos de texto entre aspas contendo `;` literal — ex.: a coluna `DIVISAO CNAE` às vezes vem como `"SERVIÇOS DE ARQUITETURA E ENGENHARIA; TESTES E ANÁLISES TÉCNICAS"`.

- Um split ingênuo por `;` (ex. fórmula de planilha simples, script sem biblioteca de CSV) desalinha todas as colunas seguintes dessa linha — foi assim que a primeira passada desta auditoria encontrou `"Médio e Grande"` (valor de `CLASSIFICACAO DE PORTE`) aparecendo dentro da coluna `CLIENTE ATIVO`.
- Com um parser de CSV correto (que respeita aspas — Power Query, `csv` do Python, etc.) o problema desaparece: **0 linhas malformadas** em todas as 9 bases.
- **Ação necessária:** garantir que a importação no Power BI (Power Query) e qualquer script auxiliar usem parser de CSV real, nunca `Split por delimitador` ingênuo direto em texto puro.

## 4. Estrutura e volume por arquivo

| Arquivo | Linhas de dados | Clientes únicos | Cobertura vs. base (85.941) | Período coberto |
|---|---|---|---|---|
| `BANCO DE DADOS.csv` (base mestre) | 85.941 | 85.941 | 100% | — (cadastral) |
| `RESERVA - COTAÇÃO - CONVERSAO.csv` | 76.964 | 51.914 | **60,41%** | jan–dez/2025 + jan–jul/2026 |
| `HISTORICO DE RESERVA.csv` | 150.000 | 28.443 | 33,10% | **jan–jun/2025 (truncado, ver §2)** |
| `VOLUME.csv` | 43.787 | 23.353 | 27,17% | jan/2024–jul/2026 (mensal, wide) |
| `AR.csv` (ativação/reativação) | 10.451 | 10.443 | 12,15% | jan–jun/2026 |
| `CONTRATOS ABERTO CLIENTE.csv` | 16.649 | 9.726 | 11,32% | contratos abertos desde 2010-10-02 |
| `NPS.csv` | 7.079 | 4.830 | 5,62% | jan/2025–jul/2026 |
| `COTACAO e CONVERSAO.csv` | 276 | — (agregado semanal) | n/a | sem chave de cliente |
| `HISTORICO DE LEADS.csv` | 29 | — (agregado ANO/DISTRITAL) | n/a | sem chave de cliente |

`COTACAO e CONVERSAO.csv` e `HISTORICO DE LEADS.csv` não têm `CODIGO_CLIENTE` — são tabelas agregadas (semana / ano-distrital), úteis como benchmark de contexto (ex.: taxa de conversão geral da carteira), mas **não entram na `MASTER_CLASSIFICADA`** por cliente.

## 5. Qualidade de campo — `BANCO DE DADOS.csv` (base mestre)

| Campo | % vazio/zero | Observação |
|---|---|---|
| `CLASSIFICACAO DE PORTE` | **93,05%** | Só existe UM valor não-vazio na base inteira (`Médio e Grande`, 6,95%) — nenhum "Pequeno", "Micro" etc. aparece. Campo praticamente inutilizável como está. |
| `PATRIMONIO LIQUIDO` | 74,92% | |
| `FATURAMENTO MENSAL` | 71,41% | Confirma a limitação já sinalizada no `readme.md` (ausência de receita/margem confiável) |
| `CNPJ` (formato correto) | 71,90% corrompido | Ver achado crítico §1 |
| `NOME GRUPO` | 1,87% | Baixo — grupo econômico é majoritariamente identificável |
| `CODIGO_CLIENTE` | 0% (íntegro) | Chave primária confiável |

**Distribuição de `CLIENTE ATIVO`:** quase um terço em cada categoria — `ATIVO` 33,45%, `INATIVO` 33,32%, `NUNCA LOCOU` 33,24%. Ou seja, **um terço da base inteira nunca fez uma locação** — isso muda o tipo de análise possível: pra esse terço, nenhuma métrica transacional (recência, frequência, valor) existe; só dá pra usar dados cadastrais/firmográficos (segmento, CNAE, porte — que por sua vez também está 93% vazio).

## 6. Avaliação geral de qualidade

**Média**, com uma ressalva importante: a chave de cliente (`CODIGO_CLIENTE`) é sólida e a cobertura das bases transacionais é razoável para um modelo de scoring — mas dois problemas (CNPJ corrompido, `HISTORICO DE RESERVA` truncado) são estruturais, não cosméticos, e precisam ser resolvidos **antes** da Etapa 2 (construção de métricas), não depois.

### Riscos que afetam diretamente conclusões futuras
1. Qualquer modelo de Score de Potencial que dependa de `FATURAMENTO MENSAL` ou `PATRIMONIO LIQUIDO` só enxerga ~25-29% da base — precisa ser tratado como proxy parcial, nunca como verdade para os outros 70%+.
2. `CLASSIFICACAO DE PORTE` não serve como variável de segmentação (93% vazio, 1 categoria só).
3. Métricas de recência/frequência de reserva calculadas sobre `HISTORICO DE RESERVA.csv` sem correção vão subestimar sistematicamente clientes ativos fora da janela jan–jun/2025.
4. `RESERVA - COTAÇÃO - CONVERSAO.csv` (60,41% de cobertura) é hoje a **melhor fonte transacional disponível** — cobre 2025 inteiro + 2026 parcial — deveria ser a base preferencial pra frequência/conversão, não o `HISTORICO DE RESERVA.csv` truncado.

## 7. Nota de compliance (Rafael)

Nenhum CPF de pessoa física foi encontrado nas colunas inspecionadas — os identificadores são `CODIGO CLIENTE` (interno) e `CNPJ` (pessoa jurídica). `NPS.csv` contém e-mail de contato do cliente PJ — tratar como dado pessoal do responsável na empresa, mascarar antes de qualquer output que saia da base (Tabela 2 — Base Classificada, conforme `PROMPT.DOCX`). Nenhum atributo sensível (raça, saúde, orientação, biometria) identificado nas bases atuais.

## 8. Próxima etapa

Com esta auditoria fechada, o André (Cientista de Dados) pode iniciar a Etapa 2 (construção de métricas) — mas as correções dos itens 1, 2 e 3 acima devem ser tratadas como **bloqueantes**, não paralelas, no [Plano de Implantação](../planejamento/plano_implantacao.md).
