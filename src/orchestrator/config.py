"""Configuración del orquestador desde variables de entorno."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Ajustes del orquestador leídos de env vars o de `.env`.

    El contrato de campos y defaults lo fija `tests/test_config.py`.
    Cada campo `foo` se lee de la env var `FOO` (mapeo por defecto de
    pydantic-settings). Las capas superiores reciben una instancia por
    inyección (ISSUE-012); ninguna lee `os.environ` directamente.
    """

    model_config = SettingsConfigDict(env_file=".env")

    http_timeout: float = 30.0
    http_retries: int = 3
    http_retry_backoff: float = 0.5
    max_upload_size: int = 10 * 1024 * 1024

    validator_service_url: str = "http://validator:8001"
    extractor_service_url: str = "http://extractor:8002"
    store_service_url: str = "http://store:8003"

    environment: Environment = "development"
    log_level: LogLevel = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
