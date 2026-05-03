# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
merge-help-csv.py — Anti-zombie CSV merge for the lens module.

Removes all existing lens rows from the target help CSV,
then appends the current module's help entries.

The module identifier is derived dynamically from column 0 of the
first data row in the module CSV (e.g. "Lens") to avoid hardcoding.
"""

import argparse
import csv
import sys
from pathlib import Path


def merge_help_csv(module_csv_path: Path, target_csv_path: Path) -> None:
    # Read module CSV
    with open(module_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            module_header = next(reader)
        except StopIteration:
            print("⚠️ Module CSV is empty — nothing to merge.")
            return
        module_rows = list(reader)

    if not module_rows:
        print("⚠️ Module CSV has no data rows — nothing to merge.")
        return

    # Derive module identifier from first non-empty data row (column 0)
    first_non_empty = next((row for row in module_rows if row and row[0].strip()), None)
    if first_non_empty is None:
        print("⚠️ Module CSV has no non-empty data rows — nothing to merge.")
        return
    module_name = first_non_empty[0]

    # Read target CSV (or create if empty)
    if target_csv_path.exists():
        with open(target_csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            try:
                target_header = next(reader)
            except StopIteration:
                # Target exists but is completely empty — treat as no header/rows
                target_header = module_header
                target_rows = []
            else:
                target_rows = list(reader)
    else:
        target_header = module_header
        target_rows = []

    # Anti-zombie: remove existing module rows (column 0 = module name)
    filtered_rows = [row for row in target_rows if not row or row[0] != module_name]

    # Append current module rows
    filtered_rows.extend(module_rows)

    # Write back
    with open(target_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(target_header)
        writer.writerows(filtered_rows)

    print(f"✅ {len(module_rows)} help entries for '{module_name}' merged into {target_csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge lens module help CSV")
    parser.add_argument("--module-csv", required=True, help="Path to module-help.csv")
    parser.add_argument("--target-csv", required=True, help="Path to target help CSV")
    args = parser.parse_args()

    module_path = Path(args.module_csv)
    target_path = Path(args.target_csv)

    if not module_path.exists():
        print(f"❌ Module CSV not found: {module_path}", file=sys.stderr)
        sys.exit(1)

    merge_help_csv(module_path, target_path)


if __name__ == "__main__":
    main()
