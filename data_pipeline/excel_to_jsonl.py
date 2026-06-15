from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def csv_to_jsonl(input_path: Path, output_path: Path) -> int:
    """Convert a UTF-8 CSV table to JSONL."""

    count = 0
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        with output_path.open("w", encoding="utf-8", newline="\n") as target:
            for row in reader:
                target.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert CSV/Excel-exported tables to JSONL.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = csv_to_jsonl(args.input, args.output)
    print(f"converted {rows} rows to {args.output}")


if __name__ == "__main__":
    main()
