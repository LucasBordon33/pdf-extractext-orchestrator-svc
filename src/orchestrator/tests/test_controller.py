import hashlib

import pytest

from orchestrator.controllers.upload_controller import UploadController
from orchestrator.exceptions import BusinessRejection, ServiceError, UpstreamError
from orchestrator.models.pipeline import StageStatus

from .helpers import (
    DEFAULT_CHECKSUM,
    DEFAULT_CONTENT,
    EXTRACTION_422,
    OVERSIZE_MSG,
    REPEATED_MSG,
    VALIDATOR_400_EXT,
    VALIDATOR_400_HEADER,
    FakeExtractor,
    FakeStore,
    FakeValidator,
    make_settings,
)


def test_full_pipeline_success_computes_checksum_and_sanitizes_name():
    content = DEFAULT_CONTENT
    validator = FakeValidator()
    extractor = FakeExtractor()
    store = FakeStore({"id": "abc123"})
    controller = UploadController(validator, extractor, store, make_settings())

    pdf, result = controller.handle_upload("dir/doc.pdf", content)

    assert pdf.id == "abc123"
    assert pdf.name == "doc.pdf"
    assert pdf.text == "texto extraido"
    assert pdf.checksum == hashlib.sha256(content).hexdigest()
    assert result.overall is StageStatus.SUCCEEDED
    assert validator.calls == [(content, "doc.pdf")]
    assert extractor.calls == [(content, "doc.pdf")]
    assert store.calls == [("doc.pdf", "texto extraido", DEFAULT_CHECKSUM, len(content))]


def test_pipeline_runs_stages_in_strict_order():
    validator = FakeValidator()
    extractor = FakeExtractor()
    store = FakeStore({"id": "1"})
    controller = UploadController(validator, extractor, store, make_settings())

    controller.handle_upload("doc.pdf", DEFAULT_CONTENT)

    assert len(validator.calls) == 1
    assert len(extractor.calls) == 1
    assert len(store.calls) == 1


def test_validator_400_is_business_rejection_and_pipeline_aborts():
    validator = FakeValidator(error=ServiceError(400, VALIDATOR_400_EXT))
    extractor = FakeExtractor()
    store = FakeStore()
    controller = UploadController(validator, extractor, store, make_settings())

    with pytest.raises(BusinessRejection) as exc_info:
        controller.handle_upload("file.pdf", DEFAULT_CONTENT)

    assert exc_info.value.detail == VALIDATOR_400_EXT
    assert exc_info.value.status_code == 400
    assert extractor.calls == []
    assert store.calls == []


def test_validator_valid_false_reason_is_business_400():
    validator = FakeValidator(result={"valid": False, "reason": VALIDATOR_400_HEADER})
    controller = UploadController(validator, FakeExtractor(), FakeStore(), make_settings())

    with pytest.raises(BusinessRejection) as exc_info:
        controller.handle_upload("file.pdf", DEFAULT_CONTENT)

    assert exc_info.value.detail == VALIDATOR_400_HEADER
    assert exc_info.value.status_code == 400


def test_extractor_422_is_business_rejection():
    extractor = FakeExtractor(error=ServiceError(422, EXTRACTION_422))
    store = FakeStore()
    controller = UploadController(FakeValidator(), extractor, store, make_settings())

    with pytest.raises(BusinessRejection) as exc_info:
        controller.handle_upload("file.pdf", DEFAULT_CONTENT)

    assert exc_info.value.detail == EXTRACTION_422
    assert exc_info.value.status_code == 422
    assert store.calls == []


def test_store_duplicate_409_is_business_duplicate():
    store = FakeStore(error=ServiceError(409, REPEATED_MSG, code="DUPLICATE_DOCUMENT"))
    controller = UploadController(FakeValidator(), FakeExtractor(), store, make_settings())

    with pytest.raises(BusinessRejection) as exc_info:
        controller.handle_upload("file.pdf", DEFAULT_CONTENT)

    assert exc_info.value.detail == REPEATED_MSG
    assert exc_info.value.status_code == 400
    assert exc_info.value.kind == "DUPLICATE_DOCUMENT"


def test_upstream_error_propagates_from_store():
    store = FakeStore(error=UpstreamError("store unreachable"))
    controller = UploadController(FakeValidator(), FakeExtractor(), store, make_settings())

    with pytest.raises(UpstreamError) as exc_info:
        controller.handle_upload("file.pdf", DEFAULT_CONTENT)

    assert str(exc_info.value) == "store unreachable"


def test_upstream_error_propagates_from_extractor():
    extractor = FakeExtractor(error=UpstreamError("connect timeout"))
    controller = UploadController(FakeValidator(), extractor, FakeStore(), make_settings())

    with pytest.raises(UpstreamError):
        controller.handle_upload("file.pdf", DEFAULT_CONTENT)


def test_store_resolved_existing_id_is_success():
    store = FakeStore({"id": "existing"})
    controller = UploadController(FakeValidator(), FakeExtractor(), store, make_settings())

    pdf, result = controller.handle_upload("doc.pdf", DEFAULT_CONTENT)

    assert pdf.id == "existing"
    assert result.overall is StageStatus.SUCCEEDED


def test_oversize_is_rejected_before_any_service_call():
    validator = FakeValidator()
    controller = UploadController(validator, FakeExtractor(), FakeStore(), make_settings(max_upload_size=8))

    with pytest.raises(BusinessRejection) as exc_info:
        controller.handle_upload("big.pdf", DEFAULT_CONTENT)

    assert exc_info.value.detail == OVERSIZE_MSG
    assert exc_info.value.status_code == 400
    assert validator.calls == []
