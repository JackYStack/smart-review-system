from app.config import Settings
from app.services.secret_store import decrypt_secret, encrypt_secret, is_encrypted


def test_secret_round_trip_and_plaintext_compatibility() -> None:
    settings = Settings(jwt_secret="test-jwt", settings_encryption_key="test-settings-key")
    encrypted = encrypt_secret("app-secret-value", settings)
    assert encrypted != "app-secret-value"
    assert is_encrypted(encrypted)
    assert decrypt_secret(encrypted, settings) == "app-secret-value"
    assert decrypt_secret("legacy-plaintext", settings) == "legacy-plaintext"


def test_secret_cannot_be_decrypted_with_another_master_key() -> None:
    first = Settings(jwt_secret="jwt-a", settings_encryption_key="key-a")
    second = Settings(jwt_secret="jwt-b", settings_encryption_key="key-b")
    encrypted = encrypt_secret("private", first)
    assert decrypt_secret(encrypted, second) == ""

