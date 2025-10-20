# scripts/suggest_values.py
import argparse, re, json
from pathlib import Path
import pandas as pd

from feature_map import FEATURES, TARGET
from utils import build_search_text, normalize_text

WORD_RE = re.compile(r"[A-Z0-9][A-Z0-9&/\-\._ ]{1,}")  # short uppercased tokens/phrases (after normalize)
MAX_NAME_LEN = 40

# Bank noise and common words to ignore
STOPWORDS_GENERAL = {
    "ACH","DEPOSIT","WITHDRAWAL","CREDIT","DEBIT","TRANSFER",
    "PAYMENT","PAID","CHECK","SALE","WEB","ONLINE","FEE","FEES",
    "MERCHANDISE","INVENTORY","PROFESSIONAL SERVICES",
    "BILLS & UTILITIES","OTHER SERVICES","OFFICE & SHIPPING",
    "GAS/AUTOMOTIVE","TRAVEL",
    "SHARE DRAFT CLEARING","CASH DEPOSIT","DEPOSITBRIDGEPLUS",
    "EXTERNAL DEPOSIT","ACH CREDIT RECEIVED","ACH DEBIT",
    "PAYMENT THANK YOU - WEB",
    "BILL","MANUAL","GPS","TAX","PMT",
}

# Move common QBO-specific noise words here
QBO_STOP_EXTRA = {
    "EXTERNAL","SHARE","DRAFT","CLEARING","EPAY","WITHDRAWAL",
    "CCD","EPMT","BUSINESSES","WWW","PAYROLL","SERVICE",
}

# Map rulebook to stopwords
STOPWORDS_BY_RB = {
    "qbo_account": STOPWORDS_GENERAL | QBO_STOP_EXTRA,
    
}

# ---------- Sanitize + unique mapping helpers ----------
def _sanitize_name(s: str) -> str:
    s = (s or "").upper().strip()
    s = s.replace("&","AND").replace("/","_").replace("-","_").replace(" ","_")
    s = re.sub(r"[^A-Z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "LABEL"
    if s[0].isdigit():
        s = "V_" + s
    return s[:MAX_NAME_LEN]

def _ensure_unique_names(labels: list[str], existing_map: dict[str, str] | None = None) -> dict[str, str]:
    """
    Stable label->ValueName without collisions:
    - Keep names already present in existing_map.
    - For new labels, sanitize and suffix if needed.
    """
    mapping = dict(existing_map or {})
    used = set(mapping.values())

    for lbl in labels:
        if lbl in mapping:
            used.add(mapping[lbl])
            continue
        base = _sanitize_name(lbl)
        name = base or "LABEL"
        i = 1
        while name in used:
            suf = f"_{i}"
            name = (base[:(64-len(suf))] + suf) if len(base)+len(suf) > 64 else base + suf
            i += 1
        mapping[lbl] = name
        used.add(name)
    return mapping

def _load_label_map(path: Path) -> dict[str, str]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}

def _save_label_map(path: Path, mapping: dict[str, str]) -> None:
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2))

# ---------- Tokenization ----------
def tokenize(txt: str, rb: str | None = None) -> list[str]:
    if not isinstance(txt, str) or not txt:
        return []
    stopset = STOPWORDS_BY_RB.get(rb or "", STOPWORDS_GENERAL)
    toks: list[str] = []
    for m in WORD_RE.findall(txt):
        t = m.strip()
        if len(t) < 3:
            continue
        if t in stopset:
            continue
        toks.append(t)
    return toks

def top_discriminative_phrases(df_pos: pd.Series,
                               df_neg: pd.Series,
                               rb: str,
                               topk=20,
                               min_len=3,
                               min_pos=5,
                               min_ratio=3.0):
    """
    Frequent tokens in positives and rare in negatives.
    Filters: min_pos occurrences in positives and ratio >= min_ratio.
    """
    from collections import Counter
    pos_toks, neg_toks = Counter(), Counter()

    for t in df_pos:
        for tok in tokenize(t, rb):
            pos_toks[tok] += 1
    for t in df_neg:
        for tok in tokenize(t, rb):
            neg_toks[tok] += 1

    scored = []
    for tok, cpos in pos_toks.items():
        if cpos < min_pos:
            continue
        cneg = neg_toks.get(tok, 0)
        ratio = cpos / (1 + cneg)
        if ratio < min_ratio:
            continue
        scored.append((ratio, cpos, cneg, tok))
    scored.sort(reverse=True)
    return scored[:topk]

def value_name_from_label(label: str) -> str:
    # kept for backward compatibility; now delegated to central mapping (see main)
    return _sanitize_name(label)

def make_alternation(tokens: list[str]) -> str:
    alts = []
    for t in tokens:
        esc = re.escape(t)
        alts.append(esc)
    return "(" + "|".join(alts) + ")"

def merge_into_template(tpl_path: Path, suggestions: dict[str, list[str]], label_map: dict[str, str], dry_run: bool):
    """
    suggestions: {label: [alt1, alt2, ...]} (normalized text)
    - Use label_map to resolve stable unique ValueName.
    - Merge alternations if already present.
    """
    if not tpl_path.exists():
        content = f"# TextFSM template for {tpl_path.stem}\nStart\n"
    else:
        content = tpl_path.read_text()

    if "\nStart" not in content:
        content = content.rstrip() + "\nStart\n"

    parts = content.split("\nStart", 1)
    header = parts[0]
    body = "Start" + (parts[1] if len(parts) > 1 else "")

    val_regex = re.compile(r"^Value\s+([A-Z0-9_]+)\s*\((.*?)\)\s*$", re.MULTILINE)
    existing = {m.group(1): m.group(2) for m in val_regex.finditer(header)}

    def parse_alts(s: str) -> list[str]:
        return [x for x in re.split(r"\|", s) if x]

    new_lines = []
    updated_header = header

    for label, toks in suggestions.items():
        valname = label_map[label]  # unique name
        alternation = make_alternation(toks)
        if valname in existing:
            prev = existing[valname]
            prev_set = set(parse_alts(prev))
            sug_set = set(parse_alts(alternation.strip("()")))
            union = sorted(prev_set | sug_set)
            merged = "(" + "|".join(union) + ")"
            updated_header = re.sub(
                rf"^Value\s+{valname}\s*\(.*?\)\s*$",
                f"Value {valname} {merged}",
                updated_header,
                flags=re.MULTILINE,
            )
        else:
            new_lines.append(f"Value {valname} {alternation}")

    if new_lines:
        updated_header = updated_header.rstrip() + "\n" + "\n".join(new_lines) + "\n"

    new_content = updated_header.rstrip() + "\n\n" + body
    if dry_run:
        print(new_content)
    else:
        tpl_path.write_text(new_content)
        print(f"✅ Template updated: {tpl_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rulebook", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--labels", help="Comma-separated subset of labels to suggest", default=None)
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing template")
    ap.add_argument("--min-pos", type=int, default=5)
    ap.add_argument("--min-ratio", type=float, default=3.0)
    args = ap.parse_args()

    rb = args.rulebook
    cols = FEATURES[rb]
    target = TARGET[rb]

    df = pd.read_csv(args.csv)
    df.columns = df.columns.str.strip()
    df[target] = df[target].map(normalize_text)
    df["__text__"] = build_search_text(df, cols)

    if args.labels:
        wanted = set([normalize_text(x) for x in args.labels.split(",") if x.strip()])
        df = df[df[target].isin(wanted)]

    labels = sorted(df[target].dropna().unique())

    # --- rulebook label map ---
    label_map_path = Path("templates") / f"{rb}_label_map.json"
    label_map = _load_label_map(label_map_path)
    label_map = _ensure_unique_names(labels, existing_map=label_map)
    _save_label_map(label_map_path, label_map)

    # --- suggestions ---
    suggestions = {}
    for label in labels:
        pos = df[df[target] == label]["__text__"]
        neg = df[df[target] != label]["__text__"]
        scored = top_discriminative_phrases(
            pos, neg, rb=rb, topk=args.topk, min_pos=args.min_pos, min_ratio=args.min_ratio
        )
        tokens = [tok for _, _, _, tok in scored]
        if tokens:
            suggestions[label] = tokens

    # --- print suggestions ---
    for lbl, toks in suggestions.items():
        print(f"\n[{lbl}] {len(toks)} suggestions:")
        for t in toks:
            print("  -", t)

    # --- write/merge TextFSM template with stable names ---
    tpl_path = Path("templates") / f"{rb}.textfsm"
    merge_into_template(tpl_path, suggestions, label_map, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
