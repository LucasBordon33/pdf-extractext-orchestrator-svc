"""Punto de entrada FastAPI: arma el grafo de dependencias y registra handlers."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from orchestrator.config import Settings
from orchestrator.controllers.document_controller import DocumentController
from orchestrator.controllers.upload_controller import UploadController
from orchestrator.exceptions import BusinessRejection, PipelineError, ServiceError
from orchestrator.routers.document_router import router as document_router
from orchestrator.routers.upload_router import router as upload_router
from orchestrator.services.service_clients import (
    ExtractorClient,
    ServiceClient,
    StoreClient,
    ValidatorClient,
)
from orchestrator.views.error_view import error_response

UPSTREAM_ERROR_PREFIX = "Error al procesar PDF: "


def create_app(settings: Settings) -> FastAPI:
    """Construye la app con sus controladores, routers y handlers."""
    app = FastAPI(title="pdf-extractext-orchestrator")

    client = ServiceClient(settings)
    validator = ValidatorClient(client, settings.validator_service_url)
    extractor = ExtractorClient(client, settings.extractor_service_url)
    store = StoreClient(client, settings.store_service_url)

    app.state.controller = UploadController(validator, extractor, store, settings)
    app.state.document_controller = DocumentController(store)

    app.include_router(upload_router)
    app.include_router(document_router)

    _register_exception_handlers(app)
    _register_health(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessRejection)
    def _handle_business(_: Request, exc: BusinessRejection) -> JSONResponse:
        return error_response(exc.status_code, exc.detail)

    @app.exception_handler(PipelineError)
    def _handle_pipeline(_: Request, exc: PipelineError) -> JSONResponse:
        return error_response(503, f"{UPSTREAM_ERROR_PREFIX}{exc.detail}")

    @app.exception_handler(ServiceError)
    def _handle_service(_: Request, exc: ServiceError) -> JSONResponse:
        return error_response(exc.status_code, exc.detail)

    @app.exception_handler(RequestValidationError)
    def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(jsonable_encoder(exc.errors()), status_code=422)


def _register_health(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "orchestrator"}


settings = Settings()
app = create_app(settings)
