import json

from orchestrator.models.pdf import PDF
from orchestrator.views.document_view import (
    build_document,
    document_list_response,
    document_response,
)

from .helpers import DEFAULT_CHECKSUM, DEFAULT_CONTENT, DOCUMENT_ID, DOCUMENT_PAYLOAD


def _pdf() -> PDF:
    return PDF(
        id=DOCUMENT_ID,
        name="doc.pdf",
        text="texto extraido",
        checksum=DEFAULT_CHECKSUM,
        size=len(DEFAULT_CONTENT),
        created_at="2026-10-09T12:30:00Z",
    )


def test_build_document_matches_store_response_shape():
    body = build_document(_pdf())
    assert body == DOCUMENT_PAYLOAD


def test_document_response_is_200_with_body():
    response = document_response(_pdf())
    assert response.status_code == 200
    assert json.loads(response.body) == DOCUMENT_PAYLOAD


def test_document_list_response_is_200_with_list():
    response = document_list_response([_pdf(), _pdf()])
    assert response.status_code == 200
    assert json.loads(response.body) == [DOCUMENT_PAYLOAD, DOCUMENT_PAYLOAD]
