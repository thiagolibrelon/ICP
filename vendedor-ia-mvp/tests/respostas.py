"""Respostas fixas do GPT (cliente simulado e avaliador C12) usadas pelos testes do Laboratório."""
import json


def cliente(msg, estado="NEGOCIANDO", revelou=(), objecao=None):
    return json.dumps({"mensagem": msg, "estado": estado, "revelou": list(revelou), "objecao": objecao})


AVALIACAO = {
    "dimensoes": {
        "diagnostico": {"nota": 8, "justificativa": "Perguntou a frequência.", "ancora": "quantos dias por mês vocês usam os carros",
                        "como_melhorar": "Pergunte quem decide.", "exemplo": "E quem aprova do lado de vocês?"},
        "challenger": {"nota": 9, "justificativa": "Mostrou a conta.", "ancora": "22 dias de diária saem mais caro que o mensal",
                       "como_melhorar": "", "exemplo": "", "trouxe_dado_concreto": "NAO", "conectou_a_situacao_do_cliente": "SIM",
                       "cliente_reagiu": "SIM", "codigos": ["CH2"]},
        "objecoes": {"nota": 6, "justificativa": "Respondeu o prazo.", "ancora": "", "como_melhorar": "Explore o medo.", "exemplo": "",
                     "respostas": [{"objecao": "OB2", "resposta": "R1", "eficacia": "media"}]},
        "qualificacao": {"nota": 2, "justificativa": "Não perguntou quem decide.", "ancora": "", "como_melhorar": "Pergunte.", "exemplo": ""},
        "adicionais": {"nota": 0, "justificativa": "Não ofereceu proteção.", "ancora": "", "como_melhorar": "", "exemplo": ""},
        "fechamento": {"nota": 7, "justificativa": "Definiu retorno.", "ancora": "frase que o vendedor nunca disse de verdade aqui",
                       "como_melhorar": "", "exemplo": "", "tipo": "FC2", "proximo_passo_claro": "SIM", "prazo_definido": "NAO"},
        "tom": {"nota": 9, "justificativa": "Cordial.", "ancora": "", "como_melhorar": "", "exemplo": ""}},
    "pontos_fortes": ["Diagnóstico"], "pontos_a_melhorar": ["Qualificação"], "resumo": "Bom começo."}
