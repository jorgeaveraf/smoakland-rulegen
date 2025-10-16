# scripts/eval_rulebook.py
import argparse, importlib.util, pandas as pd
from pathlib import Path
from utils import build_search_text, normalize_text
from feature_map import FEATURES, TARGET
from collections import Counter

def load_rules(path: Path):
    spec = importlib.util.spec_from_file_location("rules_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod._RULES  # list[(re.Pattern, label_humano)]

def predict(text: str, rules):
    for i, (pat, label) in enumerate(rules, start=1):
        if pat.search(text):
            return label, i
    return "UNKNOWN", 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rulebook", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--strict", action="store_true",
                    help="Compare raw labels (default: compare normalized).")
    ap.add_argument("--show", type=int, default=20,
                    help="How many mismatches to print.")
    args = ap.parse_args()

    rb = args.rulebook
    cols = FEATURES[rb]
    target = TARGET[rb]

    df = pd.read_csv(args.csv)
    df.columns = df.columns.str.strip()
    df[target] = df[target].map(normalize_text)
    df["__text__"] = build_search_text(df, cols)

    rules = load_rules(Path(args.rules))
    df["pred"], df["rule_id"] = zip(*df["__text__"].map(lambda t: predict(t, rules)))

    acc = (df["pred"] == df[target]).mean()
    unk = (df["pred"] == "UNKNOWN").mean()
    N = len(df)
    print(f"Accuracy: {acc:.4f} | Unknown rate: {unk:.4f} | N={N}")

    # Confusiones principales (pred -> true)
    mism = df[df["pred"] != df[target]]
    top = (mism.groupby(["pred", target]).size()
                 .sort_values(ascending=False)
                 .head(10))
    print("\nTop confusions (predicted -> true) [count]:")
    for (p,t),n in top.items():
        print(f"  {p:<16} →  {t:<20} [{n}]")

    # Muestras
    print("\nSample mismatches (up to 20):")
    show = mism[[target,"pred","__text__"]].head(20).copy()
    show.columns = [TARGET[rb], "pred_raw", "__text__"]
    print(show.to_string(index=False))

    # Hints de UNKNOWN
    unk_df = df[df["pred"]=="UNKNOWN"]
    if not unk_df.empty:
        from collections import Counter
        def bag(s):
            return [w for w in s.split(" ") if len(w)>=3]
        c = Counter()
        for t in unk_df["__text__"]:
            for w in bag(t):
                c[w] += 1
        print("\nUNKNOWN token hints (most frequent substrings):")
        for w,n in list(c.most_common(15)):
            print(f"  {w}: {n}")

    # ---- Diagnóstico de cobertura por etiqueta ----
    counts = df[target].value_counts()
    unk_as = unk_df[target].value_counts()
    recall = ((counts - unk_as).fillna(0) / counts).sort_values()
    if not recall.empty:
        print("\nWorst recall (labels con más UNKNOWN):")
        for lbl, r in recall.head(15).items():
            print(f"  {lbl:20s} {(r*100):.1f}%")
        print("\nTop UNKNOWN true labels:")
        for lbl, n in unk_as.sort_values(ascending=False).head(15).items():
            print(f"  {lbl:20s} {n}")

if __name__ == "__main__":
    main()