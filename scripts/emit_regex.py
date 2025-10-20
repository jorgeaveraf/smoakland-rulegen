# scripts/emit_regex.py
import argparse, re, json
from pathlib import Path

VAL_RE = re.compile(r"^Value\s+([A-Z0-9_]+)\s*\((.*?)\)\s*$", re.MULTILINE | re.DOTALL)

def load_json_label_map(json_path: Path) -> dict[str, str]:
    """
    JSON stored as: { "HumanLabel": "VALUE_NAME", ... }
    Invert to: { "VALUE_NAME": "HumanLabel" }
    """
    if not json_path.exists():
        return {}
    try:
        raw = json.loads(json_path.read_text())
        inv = {}
        for label, vname in raw.items():
            inv.setdefault(vname, label)
        return inv
    except Exception:
        return {}

def load_plain_overrides(path: Path) -> dict[str, str]:
    """
    Optional plain-text overrides: one 'VALUE=Label' per line.
    Returns {ValueName: HumanLabel}.
    """
    if not path or not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def parse_values_from_template(tpl_text: str) -> dict[str, str]:
    """
    Extract {ValueName: alternation} from the template (no TextFSM dependency).
    """
    values = {}
    for m in VAL_RE.finditer(tpl_text):
        name = m.group(1)
        alts = m.group(2).strip()
        # compact line breaks inside parentheses
        alts = re.sub(r"\s*\n\s*", "", alts)
        values[name] = alts
    return values

def needs_word_boundaries(pattern_source: str) -> bool:
    """
    If ALL alternants are only [A-Z0-9_ ] (space), use \\b...\\b.
    If symbols exist (:/&.- etc.), prefer letter/digit lookarounds.
    """
    src = pattern_source
    if src.startswith("(") and src.endswith(")"):
        src = src[1:-1]
    alternants = src.split("|")
    wordy = re.compile(r"^[A-Z0-9_ ]+$")
    return all(wordy.match(a.replace("\\ ", " ")) for a in alternants if a)

def build_runtime_regex_src(raw_alt: str) -> str:
    """
    Wraps alternation with (?i) and proper boundaries.
    - Supports the shorthand 'A::B::C' (AND) by converting it to lookaheads.
    - If lookaheads '(?=...)' or '.*' already exist, outer boundaries are not added.
    """
    src = raw_alt.strip()

    # 1) Support for shorthand 'A::B::C' inside Value(...) parentheses
    #    (e.g. Value FOO ((A|AA)::(B|BB)) ).
    if "::" in src and src.startswith("(") and src.endswith(")"):
        inner = src[1:-1]  # remove outer parentheses
        groups = [g.strip() for g in inner.split("::") if g.strip()]
        if len(groups) >= 2:
            # Build (?=.*(?:A|AA))(?=.*(?:B|BB))... .*
            lookaheads = "".join(rf"(?=.*(?:{g}))" for g in groups)
            src = lookaheads + r".*"

    # 2) If the pattern already uses lookaheads or is “global” with .*, skip outer boundaries
    if "(?=" in src or ".*" in src:
        return rf"(?i)(?:{src})"

    # 3) Boundary heuristic for “word-like” alternants
    if needs_word_boundaries(src):
        return rf"(?i)\b(?:{src})\b"
    else:
        return rf"(?i)(?<![A-Z0-9])(?:{src})(?![A-Z0-9])"

def emit_rules(rulebook: str, templates_dir: Path, out_dir: Path, overrides_file: str | None = None):
    tpl_path = templates_dir / f"{rulebook}.textfsm"
    tpl_text = tpl_path.read_text(encoding="utf-8")

    # 1) ValueName -> alternants
    name_to_alts = parse_values_from_template(tpl_text)

    # 2) ValueName -> HumanLabel
    json_map_path = templates_dir / f"{rulebook}_label_map.json"
    value_to_label = load_json_label_map(json_map_path)

    # 3) Optional overrides
    if overrides_file:
        value_to_label.update(load_plain_overrides(Path(overrides_file)))

    # 4) Build rules (regex source + label)
    # Allow custom ordering for specific rulebooks to reduce collisions.
    def priority_for(rulebook: str, vname: str) -> tuple:
        if rulebook == "qbo_account":
            # Higher priority (lower tuple sorts first)
            buckets = [
                {"CDTFA_TAXES", "TAXES_CDTFA_TAX", "DIRECT_LABOR_COSTS", "DIRECT_LABOR_COST",
                "COST_OF_PRODUCTION_DIRECT_LABOR_COSTS", "DELIVERY_COGS_LABOR_COST"},
                {"DELIVERY_REVENUE_CANNABIS"},
                {"DISTRIBUTION_REVENUE"},
                {"DELIVERY_REVENUE"},
                {"DUE_FROM_TPH786", "DUE_FROM_HAH_7_LLC", "INTERCOMPANY_DUE_TO_DMD"},
                {"EAST_WEST_BANK_3447", "NORTH_BAY_CREDIT_UNION_CHECKING_2035"},
                {"BANK_CHARGES_AND_FEES", "BANK_ARMOR_FEES"},
            ]
            for i, s in enumerate(buckets):
                if vname in s:
                    return (i, vname)
            return (len(buckets), vname)
        return (0, vname)

    def longest_alt_len(raw_alt: str) -> int:
        src = raw_alt.strip()
        if src.startswith("(") and src.endswith(")"):
            src = src[1:-1]
        parts = src.split("|")
        return max((len(p) for p in parts if p), default=0)

    items = []
    for vname, raw_alt in name_to_alts.items():
        regex_src = build_runtime_regex_src(raw_alt)
        label = value_to_label.get(vname, vname)  # fallback to ValueName
        prio_bucket = priority_for(rulebook, vname)[0]
        spec_len = longest_alt_len(raw_alt)
        items.append((prio_bucket, -spec_len, vname, regex_src, label))

    # final sort: by priority bucket, by longest alternant desc, by ValueName
    items.sort(key=lambda t: (t[0], t[1], t[2]))

    # 5) Write out/<rulebook>_rules.py (avoid duplicating backslashes)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_py = out_dir / f"{rulebook}_rules.py"
    lines = ["import re", "_RULES = ["]
    for _, _, _, src, label in items:
        label_literal = label.replace("'", "\\'")
        lines.append(f"    (re.compile(r'{src}'), '{label_literal}'),")
    lines.append("]")
    out_py.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Emitted {out_py} (rules: {len(items)})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rulebook", required=True)
    ap.add_argument("--templates", default="templates")
    ap.add_argument("--out", default="out")
    ap.add_argument("--label-map", help="Optional VALUE=Label overrides file", default=None)
    args = ap.parse_args()

    emit_rules(
        rulebook=args.rulebook,
        templates_dir=Path(args.templates),
        out_dir=Path(args.out),
        overrides_file=args.label_map,
    )

if __name__ == "__main__":
    main()
