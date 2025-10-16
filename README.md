# Smoakland RuleGen

Offline rule generation toolkit for categorization rulebooks using **TextFSM**.  
This tool automates the creation, maintenance, and evaluation of regex-based rulebooks used in Airflow for transaction categorization.

---

## 🐳 Quick Start (Docker Setup)

### 1️⃣ Build the container
```bash
docker compose build
```

### 2️⃣ Launch a one-off command
To run any script, prefix it with:
```bash
docker compose run --rm rulegen python <script> <args>
```

Example:
```bash
docker compose run --rm rulegen python --version
```

---

## 📁 Project Structure

```
smoakland-rulegen/
├─ data/                    # Place your labeled dataset here (ignored by Git)
│  └─ base.csv
├─ templates/               # TextFSM templates (.textfsm) per rulebook
├─ scripts/                 # CLI tools for building, suggesting, emitting & evaluating rules
├─ out/                     # Generated _RULES Python files
└─ docker-compose.yml       # Container orchestration
```

---

## 🚀 Usage Workflow

### Step 1. Prepare your dataset
Place the manually labeled dataset (ground truth) at:
```
data/base.csv
```
> ⚠️ This file should include at least:  
> `Entity, Subentity, Bank/CC #, Description, Extended Description, Payee/Vendor`  
> and the labeled columns for your rulebooks (e.g., CF Account, Dashboard, etc.).

---

### Step 2. Bootstrap a template
Creates the base TextFSM file with one entry per label.

Example:
```bash
docker compose run --rm rulegen python scripts/bootstrap_rulebook.py --rulebook qbo_account --csv data/base.csv
```

This generates:
```
templates/payee_vendor.textfsm
```

The file will contain a `Start` block with one placeholder per label.

---

### Step 3. Auto-generate & group Values (suggestions)
Use the statistical suggestion engine to build grouped variants automatically for each label.

```bash
docker compose run --rm rulegen python scripts/suggest_values.py --rulebook qbo_account --csv data/base.csv
```

#### Options:
- `--dry-run` → shows what would be written, without modifying the template.
- `--labels "AEROPAY,STRONGHOLD"` → limits to specific labels (comma-separated).
- `--topk 30` → number of top candidate tokens to include per label.

Example (preview only):
```bash
docker compose run --rm rulegen \
  python scripts/suggest_values.py --rulebook payee_vendor --csv data/base.csv --dry-run
```

After this step, your `templates/payee_vendor.textfsm` will include lines like:
```textfsm
Value AEROPAY (AEROPAY|APS?MOAKLAND|AERO[ -]?PAY)
Value STRONGHOLD (STRONGHOLD|PAYMENT|TRANSFER)
...
Start
  ^.*${AEROPAY}.* -> Record
  ^.*${STRONGHOLD}.* -> Record
```

---

### Step 4. Emit final `_RULES` (regex-only)
Converts the `.textfsm` template into a pure Python `_RULES` list used by Airflow rulebooks.

```bash
docker compose run --rm rulegen python scripts/emit_regex.py --rulebook qbo_account
```

Creates:
```
out/payee_vendor_rules.py
```

Example snippet:
```python
import re
_RULES = [
  (re.compile(r'(?i)\b(?:AEROPAY|APS?MOAKLAND|AERO[ -]?PAY)\b'), 'AEROPAY'),
  (re.compile(r'(?i)\b(?:STRONGHOLD|PAYMENT|TRANSFER)\b'), 'STRONGHOLD'),
]
```

---

### Step 5. Evaluate accuracy
Compare generated rules against your labeled dataset.

```bash
docker compose run --rm rulegen python scripts/eval_rulebook.py --rulebook qbo_account --csv data/base.csv --rules out/qbo_account_rules.py
```

Outputs example:
```
Accuracy: 0.9731 | Unknown rate: 0.0124
   Payee/Vendor        pred                                       __text__
0  AEROPAY             STRONGHOLD  TPH786 | CC 8305 | ACH - APSMOAKLAND OAK
...
```

Use this to iteratively refine your template (clean tokens, remove collisions, add variants).

---

### Step 6. Integrate into Airflow
Once accuracy and unknown rate are satisfactory:
- Copy or import the generated `_RULES` list into your Airflow rulebook module (e.g., `src/rulebook/payee_vendor.py`).
- The `infer(row)` logic remains unchanged — it now simply leverages the newly generated, compact rules.

---

## 🔁 Recommended Iteration Loop

1. Run `suggest_values.py` → auto-generate tokens.
2. Review / clean up the `Value (...)` blocks (remove generic tokens like “TPH”, “CC”, “LLC”, etc.).
3. Run `emit_regex.py` → build `_RULES`.
4. Run `eval_rulebook.py` → measure accuracy.
5. Commit the updated template and rules when metrics are good.

---

## 🧠 Tips

- Use **small subsets** with `--labels` to iterate faster before full-scale generation.
- If you see noise from columns like `Entity` or `Bank/CC #`, you can remove them from `FEATURES["payee_vendor"]` in `scripts/feature_map.py`.
- The order of Values in the template affects priority — more specific patterns should appear first.
- Avoid overfitting: if a token appears in many vendors (e.g., “TPH” or “CC 8305”), remove it manually or add it to a stoplist.

---

## ✅ Example end-to-end (payee_vendor)
```bash
docker compose build
docker compose run --rm rulegen python scripts/bootstrap_rulebook.py --rulebook payee_vendor --csv data/base.csv
docker compose run --rm rulegen python scripts/suggest_values.py --rulebook payee_vendor --csv data/base.csv
docker compose run --rm rulegen python scripts/emit_regex.py --rulebook payee_vendor
docker compose run --rm rulegen python scripts/eval_rulebook.py --rulebook payee_vendor --csv data/base.csv --rules out/payee_vendor_rules.py
```

---

## 🧩 License
Internal HQ tooling – confidential use only.
