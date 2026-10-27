import pytest
from .helpers import (
    DEFAULT_CHECKSUM,
    DEFAULT_CONTENT,
    DOCUMENT_ID,
    DOCUMENT_PAYLOAD,
    NOT_FOUND_MSG,
    FakeStore,
)

from orchestrator.controllers.document_controller import DocumentController
from orchestrator.exceptions import BusinessRejection, PipelineError, ServiceError, UpstreamError


def _controller(store: FakeStore) -> DocumentController:
    return DocumentController(store)


def test_get_document_maps_store_payload_to_pdf():
    store = FakeStore(document=DOCUMENT_PAYLOAD)
    controller = _controller(store)

    pdf = controller.get_document(DOCUMENT_ID)

    assert pdf.id == DOCUMENT_ID
    assert pdf.name == "doc.pdf"
    assert pdf.text == "texto extraido"
    assert pdf.checksum == DEFAULT_CHECKSUM
    assert pdf.size == len(DEFAULT_CONTENT)
    assert pdf.created_at == "2026-10-09T12:30:00Z"
    assert store.calls == [("get_by_id", DOCUMENT_ID)]


def test_get_document_404_is_business_rejection():
    store = FakeStore(error=ServiceError(404, NOT_FOUND_MSG, code="NOT_FOUND"))
    controller = _controller(store)

    with pytest.raises(BusinessRejection) as exc_info:
        controller.get_document("missing")

    assert exc_info.value.detail == NOT_FOUND_MSG
    assert exc_info.value.status_code == 404
    assert exc_info.value.kind == "NOT_FOUND"


def test_get_document_other_service_error_is_pipeline_error():
    store = FakeStore(error=ServiceError(500, "boom"))
    controller = _controller(store)

    with pytest.raises(PipelineError):
        controller.get_document(DOCUMENT_ID)


def test_get_document_upstream_error_propagates():
    store = FakeStore(error=UpstreamError("store unreachable"))
    controller = _controller(store)

    with pytest.raises(UpstreamError) as exc_info:
        controller.get_document(DOCUMENT_ID)

    assert str(exc_info.value) == "store unreachable"


def test_list_documents_maps_each_payload():
    store = FakeStore(documents=[DOCUMENT_PAYLOAD, DOCUMENT_PAYLOAD])
    controller = _controller(store)

    pdfs = controller.list_documents()

    assert [pdf.id for pdf in pdfs] == [DOCUMENT_ID, DOCUMENT_ID]
    assert pdfs[0].text == "texto extraido"
    assert store.calls == [("list_all",)]


def test_list_documents_upstream_error_propagates():
    store = FakeStore(error=UpstreamError("store unreachable"))
    controller = _controller(store)

    with pytest.raises(UpstreamError):
        controller.list_documents()
