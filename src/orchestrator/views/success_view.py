from fastapi.responses import JSONResponse


def build_success_response(pdf_id: str, filename: str, checksum: str, message: str) -> dict:
    return {
        "status": "ok",
        "id": pdf_id,
        "filename": filename,
        "checksum": checksum,
        "message": message,
    }


def created_response(pdf_id: str, filename: str, checksum: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=201,
        content=build_success_response(pdf_id, filename, checksum, message),
    )