import pytest

from services import llm_client


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = body if isinstance(body, str) else ""

    def json(self):
        return self._body


OK = {"choices": [{"message": {"content": "oi"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3, "completion_tokens": 1},
      "cost": {"token": {"total": 0.0012}}}


@pytest.fixture
def ligado(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "llm")
    monkeypatch.setenv("LLM_API_KEY", "segredo")
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)


def test_config(monkeypatch):
    monkeypatch.setenv("API_KEY", "chave-do-time")                   # mesma variável do classificador
    assert llm_client.api_key() == "chave-do-time" and llm_client.endpoint() == llm_client.URL_PADRAO
    for url in ("https://gw/v2", "https://gw/v2/chat/completions"):
        monkeypatch.setenv("LLM_BASE_URL", url)
        assert llm_client.endpoint() == "https://gw/v2/chat/completions"
    h = llm_client.headers()
    assert h["api_key"] == "chave-do-time" and "X-Correlation-ID" in h
    monkeypatch.setenv("LLM_AUTH_HEADER", "Authorization")
    assert llm_client.headers()["Authorization"] == "Bearer chave-do-time"
    assert llm_client.redact("x chave-do-time y") == "x *** y"


def test_tools_json_e_custo(ligado, monkeypatch):
    enviados = []
    monkeypatch.setattr(llm_client.requests, "post", lambda url, json, headers, **k: enviados.append(json) or _Resp(200, OK))
    r = llm_client.completar([], tools=[{"type": "function"}], json_mode=True)
    assert enviados[0]["tools"] and enviados[0]["response_format"] == {"type": "json_object"} and r["custo_gate"] == 0.0012


def test_gate_recusa_tools(ligado, monkeypatch):
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: _Resp(400, "Unrecognized request argument: tools"))
    with pytest.raises(llm_client.ToolsNaoSuportadas):
        llm_client.completar([], tools=[{"type": "function"}])


def test_reasoning_cai_para_low_e_sem(ligado, monkeypatch):
    efforts = []

    def post(url, json, headers, **k):
        efforts.append(json.get("reasoning_effort"))
        return _Resp(400, "Unsupported value: reasoning_effort") if "reasoning_effort" in json else _Resp(200, OK)
    monkeypatch.setattr(llm_client.requests, "post", post)
    assert llm_client.chat([])["texto"] == "oi" and efforts == ["minimal", "low", None]


def test_401_nao_repete_e_nao_vaza_chave(ligado, monkeypatch):
    n = []
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: n.append(1) or _Resp(401, "invalid key segredo"))
    with pytest.raises(llm_client.LLMUnavailable) as e:
        llm_client.chat([])
    assert len(n) == 1 and "HTTP 401" in str(e.value) and "segredo" not in str(e.value)


def test_chave_nao_esta_no_frontend():
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent
    for f in (base / "frontend").rglob("*"):
        if f.suffix not in (".html", ".js", ".css"):
            continue
        t = f.read_text(encoding="utf-8")
        assert "API_KEY" not in t and "api_key" not in t
    assert ".env" in (base / ".gitignore").read_text().splitlines()
