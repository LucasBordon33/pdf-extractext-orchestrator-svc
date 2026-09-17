import json

import pytest

from orchestrator.views.error_view import error_response
from orchestrator.views.success_view import (
    build_success_response,
    created_response,
)

from helpers import (
    EXTRACTION_422,
    OVERSIZE_MSG,
    REPEATED_MSG,
    UPLOAD_OK_MSG,
    VALIDATOR_400_EXT,
)


def test_success_body_matches_monolith_contract():
    body = build_success_response("123", "doc.pdf", "abc", UPLOAD_OK_MSG)
    assert body == {
        "status": "success",
        "id": "123",
        "filename": "doc.pdf",
        "checksum": "abc",
        "message": UPLOAD_OK_MSG,
    }


def test_created_response_is_201_with_exact_contract_body():
    response = created_response("123", "doc.pdf", "abc", UPLOAD_OK_MSG)
    assert response.status_code == 201
    assert json.loads(response.body) == {
        "status": "success",
        "id": "123",
        "filename": "doc.pdf",
        "checksum": "abc",
        "message": UPLOAD_OK_MSG,
    }


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (400, VALIDATOR_400_EXT),
        (400, OVERSIZE_MSG),
        (400, REPEATED_MSG),
        (422, EXTRACTION_422),
        (503, "Error al procesar PDF: connect timeout"),
    ],
)
def test_error_envelope_is_detail_with_correct_status(status_code, detail):
    response = error_response(status_code, detail)
    assert response.status_code == status_code
    assert json.loads(response.body) == {"detail": detail}