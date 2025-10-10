
import re
import pandas as pd

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.upper().strip()
    return " ".join(s.split())

def build_search_text(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    parts = []
    for c in cols:
        parts.append(df.get(c, "").fillna("").astype(str))
    text = pd.Series([""] * len(df), dtype="string")
    for p in parts:
        text = text.str.cat(p, sep=" | ")
    return text.map(normalize_text)

def safe_token(t: str) -> str:
    t = normalize_text(t)
    if re.fullmatch(r"[A-Z0-9_ ]+", t):
        return r"\b" + re.sub(r"\s+", r"\\s+", t) + r"\b"
    e = re.escape(t)
    e = re.sub(r"\\\s+", r"\\s+", e)
    return e

def make_alternation(tokens: list[str]) -> str:
    toks = [safe_token(t) for t in tokens if t and t.strip()]
    seen, dedup = set(), []
    for tok in toks:
        if tok not in seen:
            seen.add(tok); dedup.append(tok)
    if not dedup:
        return r"$^"
    dedup = [re.sub(r"\\b", "", t) for t in dedup]
    return r"(?i)\\b(?:" + "|".join(dedup) + r")\\b"
