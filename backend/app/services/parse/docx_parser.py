from pydantic import BaseModel, Field


class TitleNode(BaseModel):
    """Document title tree node."""

    level: int
    title_text: str
    numbering: str | None = None
    page_number: int | None = None
    children: list["TitleNode"] = Field(default_factory=list)


class StructuredDocument(BaseModel):
    """Normalized parsing output consumed by review modules."""

    file_name: str
    title_tree: list[TitleNode]
    sections: list[dict[str, object]]


def parse_docx_placeholder(file_name: str) -> StructuredDocument:
    """Return an empty structured document envelope for a DOCX file."""

    return StructuredDocument(file_name=file_name, title_tree=[], sections=[])
