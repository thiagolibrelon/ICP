import re
import unicodedata

NUM_PALAVRAS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
                "oito": 8, "nove": 9, "dez": 10, "doze": 12}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def to_int(token: str) -> int | None:
    token = token.strip()
    if token.isdigit():
        return int(token)
    return NUM_PALAVRAS.get(token)


def brl(valor: float) -> str:
    s = f"{valor:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor: float) -> str:
    v = round(valor * 100, 2)
    s = f"{v:g}".replace(".", ",")
    return f"{s}%"


def parse_brl(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def any_word(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(w)}", text) for w in words)
