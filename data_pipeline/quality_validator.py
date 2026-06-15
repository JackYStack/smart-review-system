from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = {"chunk_id", "text", "source"}


def validate_jsonl(path: Path) -> list[str]:
    """Validate a JSONL file for basic RAG chunk fields."""

    errors: list[str] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
                continue
            missing = REQUIRED_FIELDS - set(item)
            if missing:
                errors.append(f"line {line_number}: missing fields {sorted(missing)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate RAG JSONL data.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    errors = validate_jsonl(args.path)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(f"{args.path} passed")


if __name__ == "__main__":
    main()
