import asyncio
import base64
import json

import httpx
import pytest

from orchestrator.exceptions import ServiceError, UpstreamError
from orchestrator.services.service_clients import (
    ExtractorClient,
    ServiceClient,
    StoreClient,
    ValidatorClient,
)

from helpers import (
    DEFAULT_CONTENT,
    EXTRACTION_422,
    REPEATED_MSG,
    VALIDATOR_400_EXT,
    make_settings,
)


@pytest.mark.asyncio
async def test_request_retries_transport_error_with_exponential_backoff(monkeypatch):
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        raise httpx.ConnectTimeout("boom", request=request)

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(UpstreamError):
        await client.request("GET", "http://validator:8001/validate")

    assert attempts["n"] == 4
    assert delays == [0.5, 1.0, 2.0]


@pytest.mark.asyncio
async def test_request_retries_5xx_and_recovers_on_second_attempt():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(200, json={"ok": True})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))

    result = await client.request("GET", "http://validator:8001/validate")

    assert result == {"ok": True}
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_request_never_retries_4xx():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(400, json={"detail": VALIDATOR_400_EXT})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ServiceError) as exc_info:
        await client.request("GET", "http://validator:8001/validate")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == VALIDATOR_400_EXT
    assert attempts["n"] == 1


@pytest.mark.asyncio
async def test_request_carries_business_code_from_4xx_body():
    def handler(request):
        return httpx.Response(409, json={"detail": REPEATED_MSG, "code": "REPEATED"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ServiceError) as exc_info:
        await client.request("GET", "http://store:8003/pdfs")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "REPEATED"


@pytest.mark.asyncio
async def test_validator_client_sends_multipart_bytes_and_filename():
    captured = {}

    def handler(request):
        assert request.method == "POST"
        assert str(request.url).endswith("/validate")
        assert b"DEFAULT" in request.content or b"%PDF-" in request.content
        assert b'doc.pdf' in request.content
        captured["content"] = request.content
        return httpx.Response(200, json={"valid": True})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    validator = ValidatorClient(client, "http://validator:8001")

    result = await validator.validate(DEFAULT_CONTENT, "doc.pdf")

    assert result == {"valid": True}
    assert DEFAULT_CONTENT in captured["content"]


@pytest.mark.asyncio
async def test_validator_client_400_raises_business_error():
    def handler(request):
        return httpx.Response(400, json={"detail": VALIDATOR_400_EXT})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    validator = ValidatorClient(client, "http://validator:8001")

    with pytest.raises(ServiceError) as exc_info:
        await validator.validate(DEFAULT_CONTENT, "doc.pdf")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == VALIDATOR_400_EXT


@pytest.mark.asyncio
async def test_extractor_client_sends_base64_not_raw_bytes():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url).endswith("/extract")
        body = json.loads(request.content)
        assert set(body) == {"name", "content_base64"}
        assert body["name"] == "doc.pdf"
        assert base64.b64decode(body["content_base64"]) == DEFAULT_CONTENT
        return httpx.Response(200, json={"text": "texto extraido"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    extractor = ExtractorClient(client, "http://extractor:8002")

    result = await extractor.extract(DEFAULT_CONTENT, "doc.pdf")

    assert result == {"text": "texto extraido"}


@pytest.mark.asyncio
async def test_extractor_client_422_raises_business_error():
    def handler(request):
        return httpx.Response(422, json={"detail": EXTRACTION_422})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    extractor = ExtractorClient(client, "http://extractor:8002")

    with pytest.raises(ServiceError) as exc_info:
        await extractor.extract(DEFAULT_CONTENT, "doc.pdf")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == EXTRACTION_422


@pytest.mark.asyncio
async def test_store_client_posts_json_contract():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url).endswith("/pdfs")
        assert json.loads(request.content) == {
            "name": "doc.pdf",
            "text": "hola",
            "checksum": "sha123",
        }
        return httpx.Response(201, json={"id": "abc123"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = await store.store("doc.pdf", "hola", "sha123")

    assert result == {"id": "abc123"}


@pytest.mark.asyncio
async def test_store_400_repeated_on_first_attempt_is_business_error():
    requests_seen = []

    def handler(request):
        requests_seen.append(str(request.url))
        return httpx.Response(400, json={"detail": REPEATED_MSG, "code": "REPEATED"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    with pytest.raises(ServiceError) as exc_info:
        await store.store("doc.pdf", "hola", "sha123")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "REPEATED"
    assert requests_seen == ["http://store:8003/pdfs"]  # nunca hubo GET


@pytest.mark.asyncio
async def test_store_resolves_repeated_400_after_retry_via_get_by_checksum():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        url = str(request.url)
        if attempts["n"] == 1:
            raise httpx.ConnectError("timeout", request=request)
        if "/pdfs/checksum/" in url:
            assert url.endswith("/pdfs/checksum/sha123")
            return httpx.Response(200, json={"id": "existing"})
        return httpx.Response(400, json={"detail": REPEATED_MSG, "code": "REPEATED"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = await store.store("doc.pdf", "hola", "sha123")

    assert result == {"id": "existing"}
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_store_resolution_failure_is_fatal_upstream_error():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        url = str(request.url)
        if attempts["n"] == 1:
            raise httpx.ConnectError("timeout", request=request)
        if "/pdfs/checksum/" in url:
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(400, json={"detail": REPEATED_MSG, "code": "REPEATED"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    with pytest.raises(UpstreamError):
        await store.store("doc.pdf", "hola", "sha123")


@pytest.mark.asyncio
async def test_get_by_checksum_returns_existing_id():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url).endswith("/pdfs/checksum/sha123")
        return httpx.Response(200, json={"id": "existing"})

    client = ServiceClient(make_settings(), transport=httpx.MockTransport(handler))
    store = StoreClient(client, "http://store:8003")

    result = await store.get_by_checksum("sha123")

    assert result == {"id": "existing"}