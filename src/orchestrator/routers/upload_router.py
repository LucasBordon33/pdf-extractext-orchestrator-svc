"""Router HTTP de subida: recibe el multipart y delega en el controlador."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import JSONResponse

from orchestrator.controllers.upload_controller import UploadController
from orchestrator.views.success_view import created_response

UPLOAD_OK_MESSAGE = "PDF subido correctamente"

router = APIRouter()


def get_controller(request: Request) -> UploadController:
    """Devuelve el controlador configurado por la app en `app.state` (ISSUE-012)."""
    return request.app.state.controller


UploadControllerDep = Annotated[UploadController, Depends(get_controller)]


@router.post("/api/v1/upload", status_code=201)
def upload_pdf(file: UploadFile, controller: UploadControllerDep) -> JSONResponse:
    """Lee el PDF subido y devuelve la vista de éxito."""
    pdf, _ = controller.handle_upload(file.filename or "", file.file.read())
    return created_response(pdf.id, pdf.name, pdf.checksum, UPLOAD_OK_MESSAGE)
