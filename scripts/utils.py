
import re
import pandas as pd

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.upper().strip()
    return " ".join(s.split())

def build_search_text(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    text = pd.Series([""] * len(df), dtype="string")
    for c in cols:
        if c in df.columns:
            s = df[c].astype("string").fillna("")
        else:
            # Missing column, fill with empty strings
            s = pd.Series([""] * len(df), dtype="string")
        text = text.str.cat(s, sep=" | ")
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
