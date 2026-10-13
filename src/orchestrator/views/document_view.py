"""Serialización de documentos recuperados del store."""

from fastapi.responses import JSONResponse

from orchestrator.models.pdf import PDF


def build_document(pdf: PDF) -> dict[str, object]:
    """Body de un documento, espejo del `DocumentResponse` de MS4."""
    return {
        "id": pdf.id,
        "name": pdf.name,
        "checksum": pdf.checksum,
        "content": pdf.text,
        "size": pdf.size,
        "created_at": pdf.created_at,
    }


def document_response(pdf: PDF) -> JSONResponse:
    """Respuesta 200 con un único documento."""
    return JSONResponse(build_document(pdf), status_code=200)


def document_list_response(pdfs: list[PDF]) -> JSONResponse:
    """Respuesta 200 con la lista de documentos."""
    return JSONResponse([build_document(pdf) for pdf in pdfs], status_code=200)
