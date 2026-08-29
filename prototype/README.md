# Signature stamp prototype lab

Tune the Acrobat-style e-Aadhaar stamp here before locking values into `app/static/viewer.js`.

## Open the lab

```bash
./setup.sh    # once
./everify-app
```

→ http://127.0.0.1:8765/prototype/stamp-lab.html

## Validate renders (CLI, optional)

```bash
cd prototype
npm install canvas --no-save   # once
python3 validate_stamps.py
```

Targets:

- **Invalid (?)** ≥95% similarity vs `baseline_invalid.png`
- **Valid (✓)** forest green `#00a651`, tick behind text

## Reference assets

- `reference-valid-print.jpg` — Acrobat-printed reference
- `baseline_invalid.png` — PDF ? stamp @ 16×
- `stamp-config.default.json` — locked production JSON

## Files

| File | Role |
|------|------|
| `stamp-render.js` | PDF-exact 50×30 pt stamp renderer |
| `stamp-lab.html` | Interactive tuner + overlay compare |
| `validate_stamps.py` | Automated pixel checks |

When the lab looks right, export JSON and update `STAMP_CONFIG` in `app/static/viewer.js`.
