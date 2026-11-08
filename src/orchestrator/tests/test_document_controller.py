import pytest

from orchestrator.controllers.document_controller import DocumentController
from orchestrator.exceptions import BusinessRejection, PipelineError, ServiceError, UpstreamError

from .helpers import (
    DEFAULT_CHECKSUM,
    DEFAULT_CONTENT,
    DOCUMENT_ID,
    DOCUMENT_PAYLOAD,
    NOT_FOUND_MSG,
    FakeStore,
)


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


def test_update_document_maps_store_payload_to_pdf():
    store = FakeStore(document=DOCUMENT_PAYLOAD)
    controller = _controller(store)

    pdf = controller.update_document(DOCUMENT_ID, name="nuevo.pdf", size=999)

    assert pdf.id == DOCUMENT_ID
    assert pdf.name == "nuevo.pdf"
    assert pdf.text == "texto extraido"
    assert pdf.checksum == DEFAULT_CHECKSUM
    assert pdf.size == 999
    assert store.calls == [("update_by_id", DOCUMENT_ID, "nuevo.pdf", None, 999)]


def test_update_document_patches_only_provided_fields():
    store = FakeStore(document=DOCUMENT_PAYLOAD)
    controller = _controller(store)

    controller.update_document(DOCUMENT_ID, text="nuevo texto")

    assert store.calls == [("update_by_id", DOCUMENT_ID, None, "nuevo texto", None)]


def test_update_document_returns_none_when_not_found():
    store = FakeStore(document=None)
    controller = _controller(store)

    assert controller.update_document("missing", name="x.pdf") is None


def test_update_document_404_is_business_rejection():
    store = FakeStore(error=ServiceError(404, NOT_FOUND_MSG, code="DOCUMENT_NOT_FOUND"))
    controller = _controller(store)

    with pytest.raises(BusinessRejection) as exc_info:
        controller.update_document("missing", name="x.pdf")

    assert exc_info.value.detail == NOT_FOUND_MSG
    assert exc_info.value.status_code == 404
    assert exc_info.value.kind == "NOT_FOUND"


def test_update_document_other_service_error_is_pipeline_error():
    store = FakeStore(error=ServiceError(409, "dup", code="DUPLICATE_DOCUMENT"))
    controller = _controller(store)

    with pytest.raises(PipelineError):
        controller.update_document(DOCUMENT_ID, name="x.pdf")


def test_update_document_upstream_error_propagates():
    store = FakeStore(error=UpstreamError("store unreachable"))
    controller = _controller(store)

    with pytest.raises(UpstreamError) as exc_info:
        controller.update_document(DOCUMENT_ID, name="x.pdf")

    assert str(exc_info.value) == "store unreachable"
