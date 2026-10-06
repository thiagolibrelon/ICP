"""Cliente do LLM (endpoint compatível com chat/completions). A chave fica só no backend."""
import contextvars
import os
import time
import uuid
from contextlib import contextmanager
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


# ------------------------------------------------------------------ modelo por papel
# Cada chamada sabe "quem está falando": o cliente simulado, o coach ou o avaliador da nota C12. O modelo de cada papel
# vem de LLM_MODEL_<PAPEL> (ex.: LLM_MODEL_AVALIADOR) e, se não houver, de LLM_MODEL.
PAPEIS = ("cliente", "coach", "avaliador")
_ENV_DO_PAPEL: dict[str, str] = {}
_papel = contextvars.ContextVar("papel_llm", default="cliente")
_modelos = contextvars.ContextVar("modelos_llm", default=None)


@contextmanager
def papel(nome: str):
    token = _papel.set(nome)
    try:
        yield
    finally:
        _papel.reset(token)


@contextmanager
def usando_modelos(modelos: dict | None):
    token = _modelos.set({k: v for k, v in (modelos or {}).items() if v})
    try:
        yield
    finally:
        _modelos.reset(token)


def papel_atual() -> str:
    return _papel.get()


def modelo(nome_papel: str | None = None) -> str:
    p = nome_papel or _papel.get()
    base = _ENV_DO_PAPEL.get(p, p)
    return ((_modelos.get() or {}).get(p) or (_modelos.get() or {}).get(base) or os.getenv(f"LLM_MODEL_{base.upper()}")
            or os.getenv("LLM_MODEL", "gpt-5.4-mini"))


def modelos_atuais() -> dict:
    return {p: modelo(p) for p in PAPEIS}


def modelos_disponiveis() -> list[str]:
    """Sugestões para a tela (LLM_MODELOS_DISPONIVEIS, separados por vírgula) + os que já estão configurados."""
    lista = [m.strip() for m in os.getenv("LLM_MODELOS_DISPONIVEIS", "").split(",") if m.strip()]
    return list(dict.fromkeys(lista + list(modelos_atuais().values())))


def payload(messages: list[dict], max_tokens: int, json_mode: bool = False) -> dict:
    p = {"model": modelo(), "messages": messages,
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


class ToolsNaoSuportadas(LLMUnavailable):
    """O gateway recusou o parâmetro 'tools' (o agente passa a usar o protocolo JSON)."""


def completar(messages: list[dict], max_tokens: int = 1500, retries: int = 2, json_mode: bool = False,
              tools: list[dict] | None = None) -> dict:
    """Chamada crua: {"message": {...}, "tokens_entrada", "tokens_saida", "tokens_cache", "custo_gate", "finish_reason"}."""
    if mode() == "mock" or (mode() == "auto" and not configured()):
        raise LLMUnavailable("LLM desabilitado ou não configurado")
    if not configured():
        raise LLMUnavailable("Chave ausente (LLM_API_KEY ou API_KEY)")
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    last = ""
    body = payload(messages, max_tokens, json_mode)
    if tools:
        body["tools"] = tools
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
            if r.status_code == 400 and tools and "tool" in r.text.lower():
                raise ToolsNaoSuportadas(redact(f"HTTP 400: {r.text[:200]}"))
            if r.status_code >= 400:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 403, 404):  # erro de configuração: não adianta repetir
                    break
            else:
                data = r.json()
                usage = data.get("usage", {})
                choice = data["choices"][0]
                return {"message": choice.get("message") or {}, "finish_reason": choice.get("finish_reason"), "modelo": body["model"],
                        "tokens_entrada": usage.get("prompt_tokens", 0), "tokens_saida": usage.get("completion_tokens", 0),
                        "tokens_cache": (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                        # o llm-gate devolve o custo real em cost.token.total (mesma leitura do classificador)
                        "custo_gate": ((data.get("cost") or {}).get("token") or {}).get("total")}
        tentativas += 1
        time.sleep(0.5 * tentativas)
    raise LLMUnavailable(redact(f"Falha ao chamar o LLM: {last}"))


def chat(messages: list[dict], max_tokens: int = 1500, retries: int = 2, json_mode: bool = False) -> dict:
    """Atalho texto: {"texto", "tokens_entrada", "tokens_saida", "tokens_cache", "custo_gate"}."""
    r = completar(messages, max_tokens, retries, json_mode)
    texto = (r["message"].get("content") or "").strip()
    if not texto:
        raise LLMUnavailable(f"Resposta vazia do modelo (finish_reason={r['finish_reason']})")
    return {"texto": texto, **{k: r[k] for k in ("tokens_entrada", "tokens_saida", "tokens_cache", "custo_gate")}}


def endpoint_transcricao() -> str:
    """LLM_STT_URL ou a mesma base do chat trocando /chat/completions por /audio/transcriptions."""
    if os.getenv("LLM_STT_URL"):
        return os.environ["LLM_STT_URL"]
    return endpoint()[: -len("/chat/completions")] + "/audio/transcriptions"


class TranscricaoIndisponivel(LLMUnavailable):
    pass


def transcrever(audio: bytes, nome_arquivo: str = "audio.webm", mime: str = "audio/webm") -> dict:
    """Fala -> texto pelo gate (formato OpenAI /audio/transcriptions). {"texto", "modelo", "custo_gate"}."""
    if mode() == "mock" or not configured():
        raise TranscricaoIndisponivel("GPT não configurado (modo offline)")
    modelo = os.getenv("LLM_STT_MODEL", "gpt-4o-mini-transcribe")
    h = {k: v for k, v in headers().items() if k.lower() != "content-type"}  # requests monta o multipart
    try:
        r = requests.post(endpoint_transcricao(), headers=h, files={"file": (nome_arquivo, audio, mime)},
                          data={"model": modelo, "language": "pt"}, timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
                          verify=_verify())
    except Exception as e:  # noqa: BLE001
        raise TranscricaoIndisponivel(redact(f"Falha de conexão na transcrição: {type(e).__name__}: {e}"))
    if r.status_code in (404, 405):
        raise TranscricaoIndisponivel(f"O gate não tem transcrição neste endereço (HTTP {r.status_code}). Veja LLM_STT_URL.")
    if r.status_code >= 400:
        raise TranscricaoIndisponivel(redact(f"HTTP {r.status_code}: {r.text[:200]}"))
    data = r.json()
    return {"texto": (data.get("text") or "").strip(), "modelo": modelo,
            "custo_gate": ((data.get("cost") or {}).get("token") or {}).get("total")}


def _wav_silencio(segundos: float = 1.0) -> bytes:
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * segundos))
    return buf.getvalue()


def diagnosticar() -> int:
    """python -m services.llm_client  →  checa chave, DNS, proxy e faz 1 chamada mínima (não mostra a chave)."""
    import socket
    from urllib.parse import urlparse

    url = endpoint()
    host = urlparse(url).hostname or ""
    print(f"URL ............ {url}")
    print(f"Modelo ......... {os.getenv('LLM_MODEL', 'gpt-5.4-mini')}")
    for p, m in modelos_atuais().items():
        print(f"  {p:<12} . {m}")
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
    try:
        transcrever(_wav_silencio(), "teste.wav", "audio/wav")
        print(f"Áudio .......... OK: o gate transcreve ({endpoint_transcricao()})")
    except TranscricaoIndisponivel as e:
        print(f"Áudio .......... indisponível: {e}  (o botão de áudio ficará desativado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(diagnosticar())
