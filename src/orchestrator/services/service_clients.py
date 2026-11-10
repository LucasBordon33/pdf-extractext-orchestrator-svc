import base64
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
        try:
            response = self._http.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            raise UpstreamError(f"{method} {url} inalcanzable") from exc
        if response.status_code >= 500:
            raise UpstreamError(f"{method} {url} -> {response.status_code}")
        if response.status_code >= 400:
            detail, code = _error_fields(response)
            raise ServiceError(response.status_code, detail, code)
        if response.status_code == 204:
            return None
        return response.json()


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
            f"{self._base_url.resolve()}/api/v1/extract",
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

    def update_by_id(
        self,
        doc_id: str,
        name: str | None = None,
        text: str | None = None,
        size: int | None = None,
    ) -> dict[str, Any] | None:
        payload = {
            key: value
            for key, value in (("name", name), ("text", text), ("size", size))
            if value is not None
        }
        try:
            return self._client.request(
                "PATCH",
                f"{self._base_url.resolve()}{_API_PREFIX}/documents/{doc_id}",
                json=payload,
            )
        except ServiceError as exc:
            if exc.status_code == 404 and exc.code == "DOCUMENT_NOT_FOUND":
                return None
            raise

    def delete_by_id(self, doc_id: str) -> bool:
        try:
            self._client.request(
                "DELETE",
                f"{self._base_url.resolve()}{_API_PREFIX}/documents/{doc_id}",
            )
            return True
        except ServiceError as exc:
            if exc.status_code == 404 and exc.code == "DOCUMENT_NOT_FOUND":
                return False
            raise

    def _resolve_duplicate(self, checksum: str) -> dict[str, Any]:
        try:
            return self.get_by_checksum(checksum)
        except ServiceError as exc:
            raise UpstreamError(f"no se pudo resolver el duplicado: {exc.detail}") from exc
