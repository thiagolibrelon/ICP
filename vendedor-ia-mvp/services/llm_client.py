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
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def mode() -> str:
    return os.getenv("LLM_MODE", "auto").lower()


def configured() -> bool:
    return bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_BASE_URL")) and "sua_chave" not in os.getenv("LLM_API_KEY", "")


def redact(text: str) -> str:
    key = os.getenv("LLM_API_KEY")
    return text.replace(key, "***") if key else text


def chat(messages: list[dict], max_tokens: int = 500, retries: int = 2) -> dict:
    """Retorna {"texto", "tokens_entrada", "tokens_saida"} ou levanta LLMUnavailable."""
    if mode() == "mock" or (mode() == "auto" and not configured()):
        raise LLMUnavailable("LLM desabilitado ou não configurado")
    if not configured():
        raise LLMUnavailable("LLM_API_KEY/LLM_BASE_URL ausentes")
    url = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {os.environ['LLM_API_KEY']}", "Content-Type": "application/json"}
    payload = {"model": os.getenv("LLM_MODEL", "gpt-5.4-mini"), "messages": messages, "max_completion_tokens": max_tokens}
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {})
            return {"texto": data["choices"][0]["message"]["content"].strip(),
                    "tokens_entrada": usage.get("prompt_tokens", 0), "tokens_saida": usage.get("completion_tokens", 0)}
        except Exception as e:  # noqa: BLE001 - qualquer falha vira contingência
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise LLMUnavailable(redact(f"Falha ao chamar o LLM: {type(last).__name__}"))
