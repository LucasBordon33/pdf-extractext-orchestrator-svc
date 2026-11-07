"""Punto de entrada FastAPI: arma el grafo de dependencias y registra handlers.

Contratos HTTP que fija este módulo (los exige `tests/test_integration.py`):
- `GET /health` -> 200 con `{"status": "healthy", "service": "orchestrator"}`.
- `BusinessRejection` -> el status de la propia excepción, envelope `{"detail": ...}`.
- `UpstreamError` / `PipelineError` -> 503 con prefijo "Error al procesar PDF: ".
- `ServiceError` -> el status HTTP que trae la propia excepción.
- `RequestValidationError` -> 422 con la lista de errores (sin envelope).
"""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from orchestrator.config import Settings
from orchestrator.controllers.document_controller import DocumentController
from orchestrator.controllers.upload_controller import UploadController
from orchestrator.exceptions import (
    BusinessRejection,
    PipelineError,
    ServiceError,
    UpstreamError,
)
from orchestrator.infrastructure.consul import attach_health, attach_lifespan
from orchestrator.infrastructure.consul.discovery import resolve_url
from orchestrator.infrastructure.service_discovery import configure_logging
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
UPSTREAM_STATUS_CODE = 503


def create_app(settings: Settings) -> FastAPI:
    """Construye la app: grafo de dependencias, routers y handlers globales."""
    app = FastAPI(title="pdf-extractext-orchestrator")

    client = ServiceClient(settings)
    # Resolución dinámica vía Consul con fallback a la URL estática de
    # `Settings`: si Consul no está disponible, el pipeline sigue
    # funcionando igual que antes del discovery.
    validator = ValidatorClient(
        client, lambda: resolve_url("validator", settings.validator_service_url)
    )
    extractor = ExtractorClient(
        client, lambda: resolve_url("extractor", settings.extractor_service_url)
    )
    store = StoreClient(
        client, lambda: resolve_url("store", settings.store_service_url)
    )

    # Los routers resuelven sus controladores desde `app.state` (ISSUE-012).
    app.state.controller = UploadController(validator, extractor, store, settings)
    app.state.document_controller = DocumentController(store)

    app.include_router(upload_router)
    app.include_router(document_router)

    _register_exception_handlers(app)
    attach_health(app)
    # Registro en Consul al iniciar y desregistro al apagar (SIGINT/SIGTERM).
    attach_lifespan(app)
    return app


def _pipeline_failure_response(exc: PipelineError) -> JSONResponse:
    """Fallo del upstream: 503 fijo con el prefijo del contrato del monolito."""
    return error_response(UPSTREAM_STATUS_CODE, f"{UPSTREAM_ERROR_PREFIX}{exc.detail}")


def _register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores globales de dominio y de validación de FastAPI."""

    @app.exception_handler(BusinessRejection)
    def _handle_business_rejection(_: Request, exc: BusinessRejection) -> JSONResponse:
        return error_response(exc.status_code, exc.detail)

    @app.exception_handler(UpstreamError)
    def _handle_upstream_error(_: Request, exc: UpstreamError) -> JSONResponse:
        return _pipeline_failure_response(exc)

    # `PipelineError` sin subclasar cubre los 5xx del upstream mapeados en los
    # controladores; comparte la misma respuesta 503 con prefijo.
    @app.exception_handler(PipelineError)
    def _handle_pipeline_error(_: Request, exc: PipelineError) -> JSONResponse:
        return _pipeline_failure_response(exc)

    @app.exception_handler(ServiceError)
    def _handle_service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return error_response(exc.status_code, exc.detail)

    @app.exception_handler(RequestValidationError)
    def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(jsonable_encoder(exc.errors()), status_code=422)


settings = Settings()
# Logging propio para los eventos de service discovery: sin handler en el
# root logger de uvicorn, los INFO de registro/desregistro no serían visibles.
configure_logging(level=settings.log_level)
app = create_app(settings)
