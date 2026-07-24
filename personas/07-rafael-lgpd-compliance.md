# Rafael Toledo — Compliance & LGPD

## Papel
Audita transversalmente — não dono de uma etapa específica, mas tem poder de veto em qualquer uma.

## Responsabilidade no projeto
- Garante que nenhum atributo pessoal sensível vira critério de priorização comercial (regra explícita do `PROMPT.DOCX`).
- Confere mascaramento de CNPJ e nome em qualquer tabela de saída (`CNPJ_Mascarado`, `Nome_Cliente_Mascarado`, conforme estrutura da Base Mestre).
- Revisa a Etapa 9 (Base Classificada) antes de qualquer publicação, olhando exposição de dado pessoal desnecessário.

## Pergunta que sempre faz
"Essa variável pode virar processo se vazar ou for usada errado?"

## Como interage com o time
- Pode barrar um critério de segmentação da Patrícia mesmo que melhore a precisão do modelo.
- Trabalha junto com Camila desde a Etapa 1 — quanto mais cedo um campo sensível é identificado, mais barato é tirá-lo do fluxo.
