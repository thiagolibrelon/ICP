"""Avaliador C12 do Laboratório: as regras calculadas pelo sistema valem sem depender do Treino."""
import json

from services import avaliador_c12 as av
from tests.respostas import AVALIACAO


def test_regras_do_sistema_na_nota(gpt):
    gpt(json.dumps(AVALIACAO))
    hist = [{"role": "cliente", "conteudo": "Uns 22 dias por mês."},
            {"role": "vendedor", "conteudo": "Quantos dias por mês vocês usam os carros? Pergunto pra ver o melhor plano."},
            {"role": "vendedor", "conteudo": "O máximo que consigo é 6% de desconto, fica R$ 1.234,00."}]
    estado = {"revelados": ["uso"], "objecoes": [], "calculos": [], "estado_cliente": "NEGOCIANDO",
              "propostas": [{"proposta_id": "P1", "desconto_pct": 2, "tem_contrapartida": False}]}
    d = av.avaliar_conversa("C01", hist, estado)["dimensoes"]
    assert d["diagnostico"]["nota"] == round((8 + 3.3) / 2, 1) and d["diagnostico"]["ancora_verificada"] is True
    assert d["challenger"]["nota"] == 4.0                                         # sem dado concreto: limitado a 4
    assert d["disciplina_margem"]["nota"] == 1.5 and len(d["disciplina_margem"]["achados"]) == 3


def test_sem_gpt_fica_so_a_parte_do_sistema():
    r = av.avaliar_conversa("C01", [{"role": "vendedor", "conteudo": "Oi"}], {"revelados": [], "objecoes": [], "calculos": [],
                                                                           "propostas": [], "estado_cliente": "NEGOCIANDO"})
    assert r["aviso"] and set(r["dimensoes"]) == {"diagnostico", "disciplina_margem"}


def test_prompt_do_cliente_simulado_tem_a_persona():
    p = av._persona_prompt("C01", "medio")
    assert p.startswith("Você vai INTERPRETAR UM CLIENTE") and "Rogério" in p and "revela_se" in p
