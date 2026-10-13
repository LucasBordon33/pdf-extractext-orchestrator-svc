"""Serialización de respuestas de error."""

from fastapi.responses import JSONResponse


def error_response(status_code: int, detail: str) -> JSONResponse:
    """Respuesta de error con el envelope del monolito `{"detail": ...}`."""
    return JSONResponse({"detail": detail}, status_code=status_code)
