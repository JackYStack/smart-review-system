from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Load knowledge chunks into Milvus.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--collection", default="smart_review_chunks")
    args = parser.parse_args()

    print(f"ready to load {args.input} into collection {args.collection}")


if __name__ == "__main__":
    main()
