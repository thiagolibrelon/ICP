"""Cliente do LLM (endpoint compatível com chat/completions). A chave fica só no backend."""
import os
import time
from pathlib import Path

import httpx


class LLMUnavailable(Exception):
    pass


def _load_dotenv() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                os.environ.setdefault(k.strip(), v)


_load_dotenv()


def mode() -> str:
    return os.getenv("LLM_MODE", "auto").lower()


def configured() -> bool:
    return bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_BASE_URL")) and "sua_chave" not in os.getenv("LLM_API_KEY", "")


def redact(text: str) -> str:
    key = os.getenv("LLM_API_KEY")
    return text.replace(key, "***") if key else text


def endpoint() -> str:
    """Aceita a URL base ou a URL completa terminando em /chat/completions."""
    url = os.environ["LLM_BASE_URL"].rstrip("/")
    return url if url.endswith("/chat/completions") else url + "/chat/completions"


def headers() -> dict:
    """Cabeçalho da chave configurável: LLM_AUTH_HEADER (padrão Authorization) + LLM_AUTH_PREFIX (padrão 'Bearer ')."""
    nome = os.getenv("LLM_AUTH_HEADER", "Authorization")
    prefixo = os.getenv("LLM_AUTH_PREFIX", "Bearer " if nome.lower() == "authorization" else "")
    return {nome: f"{prefixo}{os.environ['LLM_API_KEY']}", "Content-Type": "application/json"}


def payload(messages: list[dict], max_tokens: int) -> dict:
    p = {"model": os.getenv("LLM_MODEL", "gpt-5.4-mini"), "messages": messages,
         "max_completion_tokens": int(os.getenv("LLM_MAX_TOKENS", max_tokens))}
    effort = os.getenv("LLM_REASONING_EFFORT", "minimal")
    if effort:  # modelos de raciocínio (gpt-5.x): raciocínio é cobrado como saída
        p["reasoning_effort"] = effort
    return p


def _verify():
    v = os.getenv("LLM_CA_BUNDLE", "").strip()
    return v if v else True


def chat(messages: list[dict], max_tokens: int = 800, retries: int = 2) -> dict:
    """Retorna {"texto", "tokens_entrada", "tokens_saida"} ou levanta LLMUnavailable."""
    if mode() == "mock" or (mode() == "auto" and not configured()):
        raise LLMUnavailable("LLM desabilitado ou não configurado")
    if not configured():
        raise LLMUnavailable("LLM_API_KEY/LLM_BASE_URL ausentes")
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    last = ""
    for attempt in range(retries + 1):
        try:
            r = httpx.post(endpoint(), json=payload(messages, max_tokens), headers=headers(), timeout=timeout, verify=_verify())
            if r.status_code >= 400:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 403, 404):  # erro de configuração: não adianta repetir
                    break
            else:
                data = r.json()
                usage = data.get("usage", {})
                texto = (data["choices"][0]["message"].get("content") or "").strip()
                if not texto:
                    last = "Resposta vazia do modelo (limite de tokens consumido pelo raciocínio?)"
                else:
                    return {"texto": texto, "tokens_entrada": usage.get("prompt_tokens", 0),
                            "tokens_saida": usage.get("completion_tokens", 0)}
        except Exception as e:  # noqa: BLE001 - qualquer falha vira contingência
            last = f"{type(e).__name__}: {e}"
        time.sleep(0.5 * (attempt + 1))
    raise LLMUnavailable(redact(f"Falha ao chamar o LLM: {last}"))
