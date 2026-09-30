"""Cliente do LLM (endpoint compatível com chat/completions). A chave fica só no backend."""
import os
import time
import uuid
from pathlib import Path

import requests


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


URL_PADRAO = "https://llm-gate-np.localiza.dev/llm-gate/v2/chat/completions"


def api_key() -> str:
    """LLM_API_KEY (.env) ou API_KEY (mesma variável do classificar_ligacoes_diario.py)."""
    k = os.getenv("LLM_API_KEY") or os.getenv("API_KEY") or ""
    return "" if "sua_chave" in k else k


def base_url() -> str:
    return os.getenv("LLM_BASE_URL") or URL_PADRAO


def configured() -> bool:
    return bool(api_key())


def redact(text: str) -> str:
    key = api_key()
    return text.replace(key, "***") if key else text


def endpoint() -> str:
    """Aceita a URL base ou a URL completa terminando em /chat/completions."""
    url = base_url().rstrip("/")
    return url if url.endswith("/chat/completions") else url + "/chat/completions"


def headers() -> dict:
    """Cabeçalho da chave configurável: LLM_AUTH_HEADER (padrão Authorization) + LLM_AUTH_PREFIX (padrão 'Bearer ')."""
    nome = os.getenv("LLM_AUTH_HEADER", "api_key")
    prefixo = os.getenv("LLM_AUTH_PREFIX", "Bearer " if nome.lower() == "authorization" else "")
    return {nome: f"{prefixo}{api_key()}", "Content-Type": "application/json",
            "X-Correlation-ID": str(uuid.uuid4())}


def payload(messages: list[dict], max_tokens: int, json_mode: bool = False) -> dict:
    p = {"model": os.getenv("LLM_MODEL", "gpt-5.4-mini"), "messages": messages,
         "max_completion_tokens": int(os.getenv("LLM_MAX_TOKENS", max_tokens))}
    if json_mode:
        p["response_format"] = {"type": "json_object"}
    effort = os.getenv("LLM_REASONING_EFFORT", "minimal")
    if effort:  # modelos de raciocínio (gpt-5.x): raciocínio é cobrado como saída
        p["reasoning_effort"] = effort
    return p


def _verify():
    v = os.getenv("LLM_CA_BUNDLE", "").strip()
    return v if v else True


def chat(messages: list[dict], max_tokens: int = 1500, retries: int = 2, json_mode: bool = False) -> dict:
    """Retorna {"texto", "tokens_entrada", "tokens_saida", "custo_gate"} ou levanta LLMUnavailable."""
    if mode() == "mock" or (mode() == "auto" and not configured()):
        raise LLMUnavailable("LLM desabilitado ou não configurado")
    if not configured():
        raise LLMUnavailable("Chave ausente (LLM_API_KEY ou API_KEY)")
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    last = ""
    body = payload(messages, max_tokens, json_mode)
    fallback_effort = ["low", None]  # igual ao script do time: se o modelo recusar o valor, tenta "low" e depois sem o parâmetro
    tentativas = 0
    while tentativas <= retries:
        try:
            # requests (e não httpx) porque no Windows ele usa o proxy configurado no sistema, como o script do time
            r = requests.post(endpoint(), json=body, headers=headers(), timeout=timeout, verify=_verify())
        except Exception as e:  # noqa: BLE001 - qualquer falha de rede vira contingência
            last = f"{type(e).__name__}: {e}"
        else:
            if r.status_code == 400 and "reasoning_effort" in body and "reasoning" in r.text.lower() and fallback_effort:
                nxt = fallback_effort.pop(0)
                if nxt:
                    body["reasoning_effort"] = nxt
                else:
                    body.pop("reasoning_effort")
                continue  # não conta como tentativa
            if r.status_code >= 400:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 403, 404):  # erro de configuração: não adianta repetir
                    break
            else:
                data = r.json()
                usage = data.get("usage", {})
                texto = (data["choices"][0]["message"].get("content") or "").strip()
                if texto:
                    return {"texto": texto, "tokens_entrada": usage.get("prompt_tokens", 0),
                            "tokens_saida": usage.get("completion_tokens", 0),
                            "tokens_cache": (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                            # o llm-gate devolve o custo real em cost.token.total (mesma leitura do classificador)
                            "custo_gate": ((data.get("cost") or {}).get("token") or {}).get("total")}
                last = f"Resposta vazia do modelo (finish_reason={data['choices'][0].get('finish_reason')})"
        tentativas += 1
        time.sleep(0.5 * tentativas)
    raise LLMUnavailable(redact(f"Falha ao chamar o LLM: {last}"))


def diagnosticar() -> int:
    """python -m services.llm_client  →  checa chave, DNS, proxy e faz 1 chamada mínima (não mostra a chave)."""
    import socket
    from urllib.parse import urlparse

    url = endpoint()
    host = urlparse(url).hostname or ""
    print(f"URL ............ {url}")
    print(f"Modelo ......... {os.getenv('LLM_MODEL', 'gpt-5.4-mini')}")
    print(f"Cabeçalho ...... {os.getenv('LLM_AUTH_HEADER', 'api_key')}")
    print(f"Chave .......... {'presente (' + str(len(api_key())) + ' caracteres)' if api_key() else 'AUSENTE — defina API_KEY ou LLM_API_KEY'}")
    proxies = {k: v for k, v in requests.utils.get_environ_proxies(url).items() if k in ("http", "https", "all")}
    print(f"Proxy (Python) . {proxies or 'nenhum (conexão direta)'}")
    try:
        print(f"DNS ............ {host} -> {socket.gethostbyname(host)}")
    except OSError as e:
        print(f"DNS ............ FALHOU ({e}). Sem proxy configurado, confira VPN/rede corporativa e a URL.")
    if not api_key():
        return 1
    os.environ["LLM_MODE"] = "llm"
    t0 = time.time()
    try:
        r = chat([{"role": "user", "content": "Responda apenas: OK"}], max_tokens=50, retries=0)
    except LLMUnavailable as e:
        print(f"Chamada ........ FALHOU: {e}")
        return 1
    print(f"Chamada ........ OK em {time.time() - t0:.1f}s | resposta: {r['texto'][:40]!r} | tokens {r['tokens_entrada']}+{r['tokens_saida']}"
          f" | custo gate: {r['custo_gate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(diagnosticar())
