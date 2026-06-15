from pathlib import Path


class PromptManager:
    """Load versioned prompt templates from disk."""

    def __init__(self, prompt_dir: Path | None = None) -> None:
        self.prompt_dir = prompt_dir or Path(__file__).parent / "prompts"

    def load(self, name: str) -> str:
        """Load a prompt template by file stem."""

        return (self.prompt_dir / f"{name}.txt").read_text(encoding="utf-8")
