import asyncio
import logging
from typing import Any

import httpx

from orchestrator.config import Settings
from orchestrator.exceptions import PipelineError, ServiceError

logger = logging.getLogger(__name__)


class ServiceClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=settings.http_timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        retries = self._settings.http_retries
        backoff = self._settings.http_retry_backoff
        last_error: httpx.RequestError | None = None

        for attempt in range(retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
                if response.status_code >= 400:
                    raise ServiceError(response.status_code, response.text)
                return response.json()
            except ServiceError:
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < retries:
                    delay = backoff * (2**attempt)
                    logger.warning(
                        "Service call to %s failed (attempt %s), retrying in %.2fs",
                        url,
                        attempt + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise PipelineError(
            f"Service unreachable after {retries + 1} attempts: {last_error}"
        ) from last_error


class ValidatorClient:
    def __init__(self, client: ServiceClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._client.request("POST", f"{self._base_url}/validate", json=data)


class ExtractorClient:
    def __init__(self, client: ServiceClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def extract(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._client.request("POST", f"{self._base_url}/extract", json=data)


class StoreClient:
    def __init__(self, client: ServiceClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def store(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._client.request("POST", f"{self._base_url}/store", json=data)