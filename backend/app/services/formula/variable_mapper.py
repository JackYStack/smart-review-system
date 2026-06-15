def normalize_variable_name(name: str) -> str:
    """Normalize formula variable names from source documents."""

    return name.strip().lower().replace(" ", "_")
