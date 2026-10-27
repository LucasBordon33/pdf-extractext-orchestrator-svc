
import pytest
from fastapi.testclient import TestClient
from .helpers import (
    DEFAULT_CHECKSUM,
    DEFAULT_CONTENT,
    DOCUMENT_ID,
    DOCUMENT_PAYLOAD,
    EXTRACTION_422,
    NOT_FOUND_MSG,
    OVERSIZE_MSG,
    REPEATED_MSG,
    UPLOAD_OK_MSG,
    VALIDATOR_400_EXT,
    FakeExtractor,
    FakeStore,
    FakeValidator,
    make_settings,
)

from orchestrator.controllers.document_controller import DocumentController
from orchestrator.controllers.upload_controller import UploadController
from orchestrator.exceptions import ServiceError, UpstreamError
from orchestrator.main import app
from orchestrator.routers.document_router import get_document_controller
from orchestrator.routers.upload_router import get_controller


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        app.dependency_overrides.clear()
        yield test_client
        app.dependency_overrides.clear()


def test_health_returns_200():
    with TestClient(app) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "orchestrator"}


def test_upload_happy_path_returns_201(client):
    validator = FakeValidator()
    extractor = FakeExtractor()
    store = FakeStore({"id": "abc123"})
    controller = UploadController(validator, extractor, store, make_settings())
    app.dependency_overrides[get_controller] = lambda: controller

    response = client.post(
        "/api/v1/upload",
        files={"file": ("doc.pdf", DEFAULT_CONTENT, "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "status": "success",
        "id": "abc123",
        "filename": "doc.pdf",
        "checksum": DEFAULT_CHECKSUM,
        "message": UPLOAD_OK_MSG,
    }
    assert extractor.calls == [(DEFAULT_CONTENT, "doc.pdf")]


def test_upload_validator_400_is_passed_through(client):
    validator = FakeValidator(error=ServiceError(400, VALIDATOR_400_EXT))
    controller = UploadController(validator, FakeExtractor(), FakeStore(), make_settings())
    app.dependency_overrides[get_controller] = lambda: controller

    response = client.post(
        "/api/v1/upload",
        files={"file": ("file.pdf", DEFAULT_CONTENT, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": VALIDATOR_400_EXT}


def test_upload_extractor_422_maps_to_fixed_message(client):
    extractor = FakeExtractor(error=ServiceError(422, EXTRACTION_422))
    controller = UploadController(FakeValidator(), extractor, FakeStore(), make_settings())
    app.dependency_overrides[get_controller] = lambda: controller

    response = client.post(
        "/api/v1/upload",
        files={"file": ("file.pdf", DEFAULT_CONTENT, "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": EXTRACTION_422}


def test_upload_duplicate_returns_400_with_monolith_message(client):
    store = FakeStore(error=ServiceError(409, REPEATED_MSG, code="DUPLICATE_DOCUMENT"))
    controller = UploadController(FakeValidator(), FakeExtractor(), store, make_settings())
    app.dependency_overrides[get_controller] = lambda: controller

    response = client.post(
        "/api/v1/upload",
        files={"file": ("file.pdf", DEFAULT_CONTENT, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": REPEATED_MSG}


def test_upload_upstream_exhausted_returns_503(client):
    extractor = FakeExtractor(error=UpstreamError("connect timeout"))
    controller = UploadController(FakeValidator(), extractor, FakeStore(), make_settings())
    app.dependency_overrides[get_controller] = lambda: controller

    response = client.post(
        "/api/v1/upload",
        files={"file": ("file.pdf", DEFAULT_CONTENT, "application/pdf")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Error al procesar PDF: connect timeout"}


def test_upload_oversize_rejected_without_reaching_validator(client):
    validator = FakeValidator()
    controller = UploadController(
        validator, FakeExtractor(), FakeStore(), make_settings(max_upload_size=8)
    )
    app.dependency_overrides[get_controller] = lambda: controller

    response = client.post(
        "/api/v1/upload",
        files={"file": ("big.pdf", DEFAULT_CONTENT, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": OVERSIZE_MSG}
    assert validator.calls == []


def test_upload_without_file_field_returns_422(client):
    response = client.post("/api/v1/upload")
    assert response.status_code == 422
    assert isinstance(response.json(), list)


def test_get_document_by_id_returns_200(client):
    store = FakeStore(document=DOCUMENT_PAYLOAD)
    app.dependency_overrides[get_document_controller] = lambda: DocumentController(store)

    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 200
    assert response.json() == DOCUMENT_PAYLOAD
    assert store.calls == [("get_by_id", DOCUMENT_ID)]


def test_get_document_not_found_returns_404(client):
    store = FakeStore(error=ServiceError(404, NOT_FOUND_MSG, code="NOT_FOUND"))
    app.dependency_overrides[get_document_controller] = lambda: DocumentController(store)

    response = client.get("/api/v1/documents/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": NOT_FOUND_MSG}


def test_list_documents_returns_200(client):
    store = FakeStore(documents=[DOCUMENT_PAYLOAD])
    app.dependency_overrides[get_document_controller] = lambda: DocumentController(store)

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json() == [DOCUMENT_PAYLOAD]
    assert store.calls == [("list_all",)]


def test_get_document_upstream_exhausted_returns_503(client):
    store = FakeStore(error=UpstreamError("connect timeout"))
    app.dependency_overrides[get_document_controller] = lambda: DocumentController(store)

    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Error al procesar PDF: connect timeout"}