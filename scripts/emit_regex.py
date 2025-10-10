
import argparse, textfsm, re
from pathlib import Path

def textfsm_to_rules(tpl_path: Path, label_map: dict[str,str]) -> list[tuple[re.Pattern,str]]:
    tpl = textfsm.TextFSM(open(tpl_path))
    rules = []
    for v in tpl.ValueNames():
        pattern = tpl._values[v].pattern
        label = label_map.get(v, v)
        pat = re.compile(rf"(?i)\\b(?:{pattern})\\b")
        rules.append((pat, label))
    return rules

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rulebook", required=True)
    ap.add_argument("--label-map", help="VALUE=Label lines", default=None)
    ap.add_argument("--templates", default="templates")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    tpl_path = Path(args.templates) / f"{args.rulebook}.textfsm"
    label_map = {}
    if args.label_map:
        for line in Path(args.label_map).read_text().splitlines():
            if "=" in line:
                k,v = line.split("=",1); label_map[k.strip()] = v.strip()

    rules = textfsm_to_rules(tpl_path, label_map)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    out_py = Path(args.out) / f"{args.rulebook}_rules.py"

    lines = ["import re","_RULES = [" ]
    for pat, label in rules:
        lines.append(f"    (re.compile(r'{pat.pattern}'), '{label}'),")
    lines.append("]")
    out_py.write_text("\n".join(lines))
    print(f"✅ Emitted {out_py}")

if __name__ == "__main__":
    main()
