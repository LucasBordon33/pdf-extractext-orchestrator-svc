"""Serialización de respuestas de éxito."""

from fastapi.responses import JSONResponse

_STATUS_SUCCESS = "success"


def build_success_response(
    pdf_id: str, filename: str, checksum: str, message: str
) -> dict[str, str]:
    """Body exacto del monolito para una subida exitosa."""
    return {
        "status": _STATUS_SUCCESS,
        "id": pdf_id,
        "filename": filename,
        "checksum": checksum,
        "message": message,
    }


def created_response(pdf_id: str, filename: str, checksum: str, message: str) -> JSONResponse:
    """Respuesta 201 con el body de éxito."""
    return JSONResponse(
        build_success_response(pdf_id, filename, checksum, message), status_code=201
    )
