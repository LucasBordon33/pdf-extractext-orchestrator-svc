from orchestrator.config import Settings


def test_defaults_when_env_missing(monkeypatch):
    for key in (
        "VALIDATOR_SERVICE_URL",
        "EXTRACTOR_SERVICE_URL",
        "STORE_SERVICE_URL",
        "HTTP_TIMEOUT",
        "HTTP_RETRIES",
        "HTTP_RETRY_BACKOFF",
        "MAX_UPLOAD_SIZE",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)
    assert settings.http_retries == 3
    assert settings.http_retry_backoff == 0.5
    assert settings.http_timeout == 30.0
    assert settings.max_upload_size == 10 * 1024 * 1024


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("HTTP_RETRIES", "5")
    monkeypatch.setenv("HTTP_RETRY_BACKOFF", "0.25")
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "2097152")

    settings = Settings(_env_file=None)
    assert settings.http_retries == 5
    assert settings.http_retry_backoff == 0.25
    assert settings.max_upload_size == 2097152