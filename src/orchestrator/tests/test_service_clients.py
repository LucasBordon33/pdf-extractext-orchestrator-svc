import base64
import json
import time

import httpx
import pytest

from orchestrator.exceptions import ServiceError, UpstreamError
from orchestrator.services.service_clients import (
    ExtractorClient,
    ServiceClient,
    StoreClient,
    ValidatorClient,
)

from .helpers import (
    DEFAULT_CONTENT,
    EXTRACTION_422,
    REPEATED_MSG,
    VALIDATOR_400_EXT,
    make_settings,
)


def test_request_retries_transport_error_with_exponential_backoff(monkeypatch):
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        raise httpx.ConnectTimeout("boom", request=request)

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    delays = []

    def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    with pytest.raises(UpstreamError):
        client.request("GET", "http://validator:8001/validate")

    assert attempts["n"] == 4
    assert delays == [0.5, 1.0, 2.0]


def test_request_retries_5xx_and_recovers_on_second_attempt():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(200, json={"ok": True})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))

    result = client.request("GET", "http://validator:8001/validate")

    assert result == {"ok": True}
    assert attempts["n"] == 2


def test_request_never_retries_4xx():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(400, json={"detail": VALIDATOR_400_EXT})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ServiceError) as exc_info:
        client.request("GET", "http://validator:8001/validate")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == VALIDATOR_400_EXT
    assert attempts["n"] == 1


def test_request_carries_business_code_from_4xx_body():
    def handler(request):
        return httpx.Response(409, json={"detail": REPEATED_MSG, "code": "DUPLICATE_DOCUMENT"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ServiceError) as exc_info:
        client.request("GET", "http://store:8003/api/v1/documents")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "DUPLICATE_DOCUMENT"


def test_validator_client_sends_json_base64_content():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url).endswith("/validate")
        body = json.loads(request.content)
        assert body["name"] == "doc.pdf"
        assert base64.b64decode(body["content_base64"]) == DEFAULT_CONTENT
        return httpx.Response(200, json={"valid": True})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    validator = ValidatorClient(client, "http://validator:8001")

    result = validator.validate(DEFAULT_CONTENT, "doc.pdf")

    assert result == {"valid": True}


def test_validator_client_400_raises_business_error():
    def handler(request):
        return httpx.Response(400, json={"detail": VALIDATOR_400_EXT})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    validator = ValidatorClient(client, "http://validator:8001")

    with pytest.raises(ServiceError) as exc_info:
        validator.validate(DEFAULT_CONTENT, "doc.pdf")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == VALIDATOR_400_EXT


def test_extractor_client_sends_raw_pdf_bytes():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url).endswith("/extract")
        assert request.headers["content-type"] == "application/pdf"
        assert request.content == DEFAULT_CONTENT
        return httpx.Response(200, json={"content": "texto extraido", "page_count": 1})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    extractor = ExtractorClient(client, "http://extractor:8002")

    result = extractor.extract(DEFAULT_CONTENT, "doc.pdf")

    assert result == {"content": "texto extraido", "page_count": 1}


def test_extractor_client_422_raises_business_error():
    def handler(request):
        return httpx.Response(
            422, json={"error_code": "EMPTY_EXTRACTION", "message": EXTRACTION_422}
        )

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    extractor = ExtractorClient(client, "http://extractor:8002")

    with pytest.raises(ServiceError) as exc_info:
        extractor.extract(DEFAULT_CONTENT, "doc.pdf")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == EXTRACTION_422
    assert exc_info.value.code == "EMPTY_EXTRACTION"


def test_store_client_posts_json_contract():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url).endswith("/api/v1/store")
        assert json.loads(request.content) == {
            "name": "doc.pdf",
            "text": "hola",
            "checksum": "sha123",
            "size": 0,
        }
        return httpx.Response(201, json={"id": "abc123", "checksum": "sha123"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = store.store("doc.pdf", "hola", "sha123")

    assert result == {"id": "abc123", "checksum": "sha123"}


def test_store_client_sends_size_when_provided():
    def handler(request):
        assert json.loads(request.content)["size"] == len(DEFAULT_CONTENT)
        return httpx.Response(201, json={"id": "abc123"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    store.store("doc.pdf", "hola", "sha123", len(DEFAULT_CONTENT))


def test_store_409_duplicate_on_first_attempt_is_business_error():
    requests_seen = []

    def handler(request):
        requests_seen.append(str(request.url))
        return httpx.Response(409, json={"error_code": "DUPLICATE_DOCUMENT", "message": REPEATED_MSG})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    with pytest.raises(ServiceError) as exc_info:
        store.store("doc.pdf", "hola", "sha123")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "DUPLICATE_DOCUMENT"
    assert requests_seen == ["http://store:8003/api/v1/store"]  # nunca hubo GET


def test_store_resolves_duplicate_after_retry_via_get_by_checksum():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        url = str(request.url)
        if attempts["n"] == 1:
            raise httpx.ConnectError("timeout", request=request)
        if "/documents/checksum/" in url:
            assert url.endswith("/api/v1/documents/checksum/sha123")
            return httpx.Response(200, json={"id": "existing"})
        return httpx.Response(
            409, json={"error_code": "DUPLICATE_DOCUMENT", "message": REPEATED_MSG}
        )

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = store.store("doc.pdf", "hola", "sha123")

    assert result == {"id": "existing"}
    assert attempts["n"] == 3


def test_store_resolution_failure_is_fatal_upstream_error():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        url = str(request.url)
        if attempts["n"] == 1:
            raise httpx.ConnectError("timeout", request=request)
        if "/documents/checksum/" in url:
            return httpx.Response(404, json={"error_code": "NOT_FOUND", "message": "not found"})
        return httpx.Response(
            409, json={"error_code": "DUPLICATE_DOCUMENT", "message": REPEATED_MSG}
        )

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    with pytest.raises(UpstreamError):
        store.store("doc.pdf", "hola", "sha123")


def test_get_by_checksum_returns_existing_document():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url).endswith("/api/v1/documents/checksum/sha123")
        return httpx.Response(200, json={"id": "existing"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = store.get_by_checksum("sha123")

    assert result == {"id": "existing"}


def test_get_by_id_returns_document():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url).endswith("/api/v1/documents/abc123")
        return httpx.Response(200, json={"id": "abc123", "content": "texto"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = store.get_by_id("abc123")

    assert result == {"id": "abc123", "content": "texto"}


def test_list_all_returns_documents():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url).endswith("/api/v1/documents")
        return httpx.Response(200, json=[{"id": "abc123"}])

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = store.list_all()

    assert result == [{"id": "abc123"}]
