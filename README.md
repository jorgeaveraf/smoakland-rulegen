
# Smoakland RuleGen

Offline rule generation toolkit for categorization rulebooks using TextFSM.
This repo generates `_RULES` Python files for production use (Airflow rulebooks).

## Usage
1. Place your labeled dataset at `data/base.csv`.
2. Bootstrap a template for a rulebook:
   ```bash
   python scripts/bootstrap_rulebook.py --rulebook qbo_sub_account --csv data/base.csv
   ```
3. Edit the generated `templates/<rulebook>.textfsm` to group variants.
4. Emit `_RULES`:
   ```bash
   python scripts/emit_regex.py --rulebook qbo_sub_account
   ```
5. Evaluate accuracy:
   ```bash
   python scripts/eval_rulebook.py --rulebook qbo_sub_account --csv data/base.csv --rules out/qbo_sub_account_rules.py
   ```
