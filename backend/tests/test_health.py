from unittest.mock import Mock, patch

from app.api.health import _check_database, _check_minio, live, ready


def test_live_does_not_check_external_dependencies() -> None:
    response = live()
    assert response.status == "ok"
    assert response.dependencies == {}


def test_readiness_is_ok_when_database_and_bucket_are_available() -> None:
    db = Mock()
    client = Mock()
    client.bucket_exists.return_value = True
    with patch("app.api.health.minio_storage.get_client", return_value=client):
        response = ready(db)
    assert response.status == "ok"
    assert response.dependencies["database"].status == "ok"
    assert response.dependencies["object_storage"].status == "ok"


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    db = Mock()
    db.execute.side_effect = RuntimeError("secret database error")
    client = Mock()
    client.bucket_exists.return_value = True
    with patch("app.api.health.minio_storage.get_client", return_value=client):
        response = ready(db)
    assert response.status_code == 503
    assert b"secret database error" not in response.body


def test_minio_missing_bucket_is_not_ready() -> None:
    client = Mock()
    client.bucket_exists.return_value = False
    with patch("app.api.health.minio_storage.get_client", return_value=client):
        result = _check_minio()
    assert result.status == "error"
    assert "does not exist" in result.detail


def test_database_error_does_not_leak_exception_message() -> None:
    db = Mock()
    db.execute.side_effect = RuntimeError("password=must-not-leak")
    result = _check_database(db)
    assert result.status == "error"
    assert "must-not-leak" not in result.detail
