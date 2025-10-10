
import argparse, pandas as pd
from pathlib import Path
from utils import build_search_text, normalize_text
from feature_map import FEATURES, TARGET

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
    df["__text__"] = build_search_text(df, cols)
    df[target] = df[target].map(normalize_text)

    top = (
        df.groupby(target)["__text__"]
          .apply(lambda s: pd.Series(s.unique()[:50]))
          .reset_index(level=0)
          .groupby(level=0)[0]
          .apply(list)
    )

    Path(args.out).mkdir(parents=True, exist_ok=True)
    tpl = ["# TextFSM template for " + rb, "Start"]
    for label, examples in top.items():
        if not isinstance(label, str) or not label.strip():
            continue
        val_name = label.upper().replace("&","AND").replace(" ","_").replace("/","_").replace("-","_")
        tpl.append(f"  ^.*${{{val_name}}}.* -> Record")
    Path(args.out, f"{rb}.textfsm").write_text("\n".join(tpl))
    print(f"✅ Bootstrap template written to templates/{rb}.textfsm")

if __name__ == "__main__":
    main()
