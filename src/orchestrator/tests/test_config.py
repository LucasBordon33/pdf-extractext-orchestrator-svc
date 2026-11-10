from orchestrator.config import Settings


def test_defaults_when_env_missing(monkeypatch):
    for key in (
        "VALIDATOR_SERVICE_URL",
        "EXTRACTOR_SERVICE_URL",
        "STORE_SERVICE_URL",
        "HTTP_TIMEOUT",
        "MAX_UPLOAD_SIZE",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)
    assert settings.http_timeout == 30.0
    assert settings.max_upload_size == 10 * 1024 * 1024


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "2097152")

    settings = Settings(_env_file=None)
    assert settings.max_upload_size == 2097152