from pydantic import BaseModel, Field


class ParseQuality(BaseModel):
    """Parsing quality signal."""

    title_tree_score: float = Field(ge=0.0, le=1.0)
    table_score: float = Field(ge=0.0, le=1.0)
    ocr_score: float = Field(ge=0.0, le=1.0)

    @property
    def passed(self) -> bool:
        """Return whether the parsed document is good enough for automatic review."""

        return min(self.title_tree_score, self.table_score, self.ocr_score) >= 0.75
