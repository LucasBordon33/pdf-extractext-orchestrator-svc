"""Router HTTP de consulta: recupera documentos del store a través del controlador."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from orchestrator.controllers.document_controller import DocumentController
from orchestrator.views.document_view import document_list_response, document_response

router = APIRouter()


def get_document_controller(request: Request) -> DocumentController:
    """Devuelve el controlador de consulta configurado en `app.state` (ISSUE-012)."""
    return request.app.state.document_controller


DocumentControllerDep = Annotated[DocumentController, Depends(get_document_controller)]


@router.get("/api/v1/documents")
def list_documents(controller: DocumentControllerDep) -> JSONResponse:
    """Lista todos los documentos almacenados."""
    return document_list_response(controller.list_documents())


@router.get("/api/v1/documents/{doc_id}")
def get_document(doc_id: str, controller: DocumentControllerDep) -> JSONResponse:
    """Devuelve un documento por su id."""
    return document_response(controller.get_document(doc_id))
