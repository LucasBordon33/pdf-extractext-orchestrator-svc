"""Excepciones de dominio del orquestador."""

from typing import Literal

RejectionKind = Literal["VALIDATION_ERROR", "EXTRACTION_ERROR", "DUPLICATE_DOCUMENT"]


class ServiceError(Exception):
    """Error HTTP de un microservicio ascendente; no se reintenta."""

    def __init__(self, status_code: int, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class PipelineError(ServiceError):
    """Servicio inalcanzable tras agotar reintentos (503 por defecto)."""

    def __init__(self, detail: str, status_code: int = 503, code: str | None = None) -> None:
        super().__init__(status_code, detail, code)


class UpstreamError(PipelineError):
    """Fallo definitivo del upstream (reintentos agotados o resolución fallida)."""


class BusinessRejection(Exception):
    """Rechazo de negocio: validación, duplicado u oversize."""

    def __init__(self, detail: str, kind: RejectionKind, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.kind = kind
        self.status_code = status_code
