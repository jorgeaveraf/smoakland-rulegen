# scripts/bootstrap_rulebook.py
import argparse, json, pandas as pd
from pathlib import Path
from utils import build_search_text, normalize_text
from feature_map import FEATURES, TARGET
from suggest_values import _sanitize_name, _ensure_unique_names, _load_label_map, _save_label_map

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rulebook", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default="templates")
    args = ap.parse_args()

    rb = args.rulebook
    cols = FEATURES[rb]
    target = TARGET[rb]

    df = pd.read_csv(args.csv)
    df.columns = df.columns.str.strip()
    df["__text__"] = build_search_text(df, cols)
    df[target] = df[target].map(normalize_text)

    labels = sorted(df[target].dropna().unique())

    # --- build stable & unique label map ---
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    label_map_path = out_dir / f"{rb}_label_map.json"
    label_map = _load_label_map(label_map_path)         # keep existing
    label_map = _ensure_unique_names(labels, label_map) # add new without collisions
    _save_label_map(label_map_path, label_map)

    # --- build base TextFSM template ---
    tpl_lines = [f"# TextFSM template for {rb}", "Start"]
    for label in labels:
        val_name = label_map[label]  # safe & unique name
        tpl_lines.append(f"  ^.*${{{val_name}}}.* -> Record")

    out_path = out_dir / f"{rb}.textfsm"
    out_path.write_text("\n".join(tpl_lines))
    print(f"✅ Bootstrap template written to {out_path}")
    print(f"🗂️  Label map written to {label_map_path}")

if __name__ == "__main__":
    main()
