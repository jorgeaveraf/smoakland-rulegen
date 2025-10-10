
import argparse, importlib.util, pandas as pd
from pathlib import Path
from utils import build_search_text, normalize_text
from feature_map import FEATURES, TARGET

def load_rules(path: Path):
    spec = importlib.util.spec_from_file_location("rules_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod._RULES

def predict(text: str, rules):
    for i,(pat,label) in enumerate(rules, start=1):
        if pat.search(text):
            return label, i
    return "UNKNOWN", 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rulebook", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--rules", required=True)
    args = ap.parse_args()

    rb = args.rulebook
    cols = FEATURES[rb]
    target = TARGET[rb]
    df = pd.read_csv(args.csv)
    df["__text__"] = build_search_text(df, cols)
    df[target] = df[target].map(normalize_text)

    rules = load_rules(Path(args.rules))
    df["pred"], df["rule_id"] = zip(*df["__text__"].map(lambda t: predict(t, rules)))
    acc = (df["pred"] == df[target]).mean()
    unk = (df["pred"] == "UNKNOWN").mean()
    print(f"Accuracy: {acc:.4f} | Unknown rate: {unk:.4f}")
    print(df[df["pred"] != df[target]][[target,"pred","__text__"]].head(20).to_string(index=False))

if __name__ == "__main__":
    main()
