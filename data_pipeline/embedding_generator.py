from __future__ import annotations

import argparse
import json
from pathlib import Path


def attach_placeholder_embeddings(input_path: Path, output_path: Path) -> int:
    """Attach deterministic placeholder vectors for local pipeline tests."""

    count = 0
    with input_path.open("r", encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as target:
        for line in source:
            if not line.strip():
                continue
            item = json.loads(line)
            item["embedding"] = [0.0, 0.0, 0.0]
            target.write(json.dumps(item, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate placeholder embeddings.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = attach_placeholder_embeddings(args.input, args.output)
    print(f"generated embeddings for {rows} chunks")


if __name__ == "__main__":
    main()
