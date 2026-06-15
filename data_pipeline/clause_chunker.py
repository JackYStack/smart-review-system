from __future__ import annotations

import argparse
import json
from pathlib import Path


def chunk_clause(clause: dict[str, str]) -> dict[str, str]:
    """Build one retrievable knowledge chunk from a clause row."""

    title = clause.get("title", "")
    text = clause.get("text", "")
    return {
        "chunk_id": clause.get("clause_id", ""),
        "source": clause.get("source", ""),
        "text": f"{title}\n{text}".strip(),
    }


def build_chunks(input_path: Path, output_path: Path) -> int:
    """Convert clause JSONL to knowledge chunk JSONL."""

    count = 0
    with input_path.open("r", encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as target:
        for line in source:
            if not line.strip():
                continue
            target.write(json.dumps(chunk_clause(json.loads(line)), ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk regulation clauses for RAG.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = build_chunks(args.input, args.output)
    print(f"built {rows} chunks")


if __name__ == "__main__":
    main()
