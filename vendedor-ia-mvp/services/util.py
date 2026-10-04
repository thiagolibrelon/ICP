import re
import unicodedata


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


def brl(valor: float) -> str:
    s = f"{valor:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_brl(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def palavras(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(text))
