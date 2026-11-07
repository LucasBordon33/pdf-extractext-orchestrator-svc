import base64
import time
from collections.abc import Callable
from typing import Any

import httpx

from orchestrator.config import Settings
from orchestrator.exceptions import ServiceError, UpstreamError

BaseUrlSource = str | Callable[[], str]


class _BaseUrl:

    def __init__(self, source: BaseUrlSource) -> None:
        self._source: BaseUrlSource = source

    def resolve(self) -> str:
        url = self._source() if callable(self._source) else self._source
        return url.rstrip("/")


def _error_fields(response: httpx.Response) -> tuple[str, str | None]:
    try:
        body = response.json()
    except ValueError:
        return response.text, None
    if not isinstance(body, dict):
        return response.text, None
    if "error_code" in body:
        return str(body.get("message", "")), body.get("error_code")
    if "detail" in body:
        return str(body["detail"]), body.get("code")
    return response.text, body.get("code")


class ServiceClient:

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._http = httpx.Client(transport=transport, timeout=settings.http_timeout)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        retries = self._settings.http_retries
        for attempt in range(retries + 1):
            try:
                response = self._http.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if attempt == retries:
                    raise UpstreamError(f"{method} {url} inalcanzable") from exc
                time.sleep(self._retry_delay(attempt))
                continue
            if response.status_code >= 500:
                if attempt == retries:
                    raise UpstreamError(f"{method} {url} -> {response.status_code}")
                time.sleep(self._retry_delay(attempt))
                continue
            if response.status_code >= 400:
                if attempt > 0:
                    raise UpstreamError(f"{method} {url} -> {response.status_code} tras reintentos")
                detail, code = _error_fields(response)
                raise ServiceError(response.status_code, detail, code)
            return response.json()
        raise UpstreamError(f"{method} {url} sin respuesta")

    def _retry_delay(self, attempt: int) -> float:
        return self._settings.http_retry_backoff * 2**attempt


class ValidatorClient:

    def __init__(self, client: ServiceClient, base_url: BaseUrlSource) -> None:
        self._client = client
        self._base_url = _BaseUrl(base_url)

    def validate(self, content: bytes, filename: str) -> dict[str, Any]:
        payload = {
            "name": filename,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        return self._client.request(
            "POST", f"{self._base_url.resolve()}/validate", json=payload
        )


class ExtractorClient:

    def __init__(self, client: ServiceClient, base_url: BaseUrlSource) -> None:
        self._client = client
        self._base_url = _BaseUrl(base_url)

    def extract(self, content: bytes, filename: str) -> dict[str, Any]:
        return self._client.request(
            "POST",
            f"{self._base_url.resolve()}/extract",
            content=content,
            headers={"Content-Type": "application/pdf"},
        )


_API_PREFIX = "/api/v1"


class StoreClient:

    def __init__(self, client: ServiceClient, base_url: BaseUrlSource) -> None:
        self._client = client
        self._base_url = _BaseUrl(base_url)

    def store(self, name: str, text: str, checksum: str, size: int = 0) -> dict[str, Any]:
        payload = {"name": name, "text": text, "checksum": checksum, "size": size}
        try:
            return self._client.request(
                "POST", f"{self._base_url.resolve()}{_API_PREFIX}/store", json=payload
            )
        except UpstreamError:
            return self._resolve_duplicate(checksum)

    def get_by_id(self, doc_id: str) -> dict[str, Any]:
        return self._client.request(
            "GET", f"{self._base_url.resolve()}{_API_PREFIX}/documents/{doc_id}"
        )

    def get_by_checksum(self, checksum: str) -> dict[str, Any]:
        return self._client.request(
            "GET", f"{self._base_url.resolve()}{_API_PREFIX}/documents/checksum/{checksum}"
        )

    def list_all(self) -> list[dict[str, Any]]:
        return self._client.request(
            "GET", f"{self._base_url.resolve()}{_API_PREFIX}/documents"
        )

    def _resolve_duplicate(self, checksum: str) -> dict[str, Any]:
        try:
            return self.get_by_checksum(checksum)
        except ServiceError as exc:
            raise UpstreamError(f"no se pudo resolver el duplicado: {exc.detail}") from exc
