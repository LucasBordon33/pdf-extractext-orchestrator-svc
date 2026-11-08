"""Router HTTP de consulta: recupera documentos del store a través del controlador."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from orchestrator.controllers.document_controller import DocumentController
from orchestrator.infrastructure.consul.discovery import fallback_active_for, fallback_services
from orchestrator.views.document_view import document_list_response, document_response

router = APIRouter()

NOT_FOUND_BY_ID_MESSAGE = "No document found for the given id"


class UpdateDocumentRequest(BaseModel):
    name: str | None = None
    text: str | None = None
    size: int | None = None


def get_document_controller(request: Request) -> DocumentController:
    """Devuelve el controlador de consulta configurado en `app.state` (ISSUE-012)."""
    return request.app.state.document_controller


DocumentControllerDep = Annotated[DocumentController, Depends(get_document_controller)]


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Respuesta de error con el mismo envelope que MS4."""
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message},
    )


@router.get("/api/v1/documents")
def list_documents(controller: DocumentControllerDep) -> JSONResponse:
    """Lista todos los documentos almacenados."""
    return document_list_response(controller.list_documents())


@router.get("/api/v1/documents/{doc_id}")
def get_document(doc_id: str, controller: DocumentControllerDep) -> JSONResponse:
    """Devuelve un documento por su id."""
    return document_response(controller.get_document(doc_id))


@router.delete("/api/v1/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str, controller: DocumentControllerDep) -> Response:
    """Elimina un documento por su id; 204 si se borró, 404 si no existía."""
    deleted = controller.delete_document(doc_id)
    if not deleted:
        return _error_response(404, "DOCUMENT_NOT_FOUND", NOT_FOUND_BY_ID_MESSAGE)
    return Response(status_code=204)


@router.patch("/api/v1/documents/{doc_id}")
def update_document(
    doc_id: str, payload: UpdateDocumentRequest, controller: DocumentControllerDep
) -> JSONResponse:
    """Actualiza metadatos de un documento; 200 si se modificó, 404 si no existía."""
    pdf = controller.update_document(
        doc_id, name=payload.name, text=payload.text, size=payload.size
    )
    if pdf is None:
        return _error_response(404, "DOCUMENT_NOT_FOUND", NOT_FOUND_BY_ID_MESSAGE)
    return document_response(pdf)


@router.get("/health/discovery")
def discovery_health() -> JSONResponse:
    """Estado del plano de service discovery.

    Indica qué servicios están usando URL estática (fallback) porque
    Consul no respondió o no devolvió instancias saludables.
    """
    return JSONResponse(
        {
            "status": "healthy",
            "fallback_active": list(fallback_services()),
            "services": {
                "validator": fallback_active_for("validator"),
                "extractor": fallback_active_for("extractor"),
                "store": fallback_active_for("store"),
            },
        }
    )