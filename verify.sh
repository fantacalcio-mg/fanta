#!/usr/bin/env bash
set -e

echo "=== M1+M2+M3 Verification Gate ==="
echo

# 1. Install dependencies
echo "1. Installing dependencies with uv..."
uv sync --quiet
echo "   ✓ Done"
echo

# 2. Run ruff lint
echo "2. Running ruff lint..."
uv run ruff check src/ tests/
echo "   ✓ Lint passed"
echo

# 3. Run ruff format check
echo "3. Running ruff format check..."
uv run ruff format --check src/ tests/
echo "   ✓ Format passed"
echo

# 4. Run pytest (includes M1 + M2+M3 tests)
echo "4. Running pytest..."
uv run pytest tests/ -v
echo "   ✓ Tests passed"
echo

# 5. Validate config
echo "5. Validating config with 'fanta status'..."
uv run fanta status
echo "   ✓ Config valid"
echo

# 6. Stage listone
echo "6. Running 'fanta stage' (listone)..."
uv run fanta stage --source listone_ufficiale
echo "   ✓ Stage listone passed"
echo

# 7. Build listone
echo "7. Running 'fanta build' (listone)..."
uv run fanta build --source listone_ufficiale
echo "   ✓ Build listone passed"
echo

# 8. Verify M1 gates
echo "8. Running 'fanta verify' (M1 gates)..."
uv run fanta verify
echo "   ✓ Verify M1 passed"
echo

# 9. Stage storico (if files exist)
if [ -d "data/raw/storico_aggregato" ] && [ "$(find data/raw/storico_aggregato -name '*.xlsx' | wc -l)" -gt 0 ]; then
  echo "9. Running 'fanta stage' (storico_aggregato)..."
  uv run fanta stage --source storico_aggregato
  echo "   ✓ Stage storico passed"
  echo

  # 10. Build storico
  echo "10. Running 'fanta build' (storico_aggregato)..."
  uv run fanta build --source storico_aggregato
  echo "   ✓ Build storico passed"
  echo

  echo "=== M1+M2+M3 VERIFICATION PASSED ==="
else
  echo "=== M1 VERIFICATION PASSED ==="
  echo ""
  echo "NOTE: M2+M3 require real storico XLSX files:"
  echo "  1. Download 4 seasons from Fantacalcio.it Statistiche"
  echo "  2. Save to: data/raw/storico_aggregato/{stagione}/stats.xlsx"
  echo "     (stagioni: 2024-25, 2023-24, 2022-23, 2021-22)"
  echo "  3. Run: ./verify.sh"
fi
