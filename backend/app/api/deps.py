from app.config import Settings, get_settings


def settings_dependency() -> Settings:
    """Expose application settings as a dependency."""

    return get_settings()
