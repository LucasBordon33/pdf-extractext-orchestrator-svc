"""Manejo centralizado de errores de servicios upstream."""

from collections.abc import Callable
from typing import TypeVar

from orchestrator.exceptions import (
    BusinessRejection,
    PipelineError,
    RejectionKind,
    ServiceError,
    UpstreamError,
)

T = TypeVar("T")


def handle_service_errors[T](
    action: Callable[[], T],
    rejection_mapper: Callable[[ServiceError], Exception],
) -> T:
    """Ejecuta `action` mapeando errores de servicio a excepciones de dominio.

    - `UpstreamError` se propaga tal cual.
    - `ServiceError` se transforma mediante `rejection_mapper` y se encadena
      con la causa original (`from exc`).
    """
    try:
        return action()
    except UpstreamError:
        raise
    except ServiceError as exc:
        raise rejection_mapper(exc) from exc


def map_store_error(
    exc: ServiceError,
    *,
    duplicate_kind: RejectionKind | None = None,
    duplicate_status: int | None = None,
    rejection_status: int | None = None,
    not_found_status: int | None = None,
) -> Exception:
    """Mapea un ServiceError del store a BusinessRejection o PipelineError.

    - `duplicate_kind` / `duplicate_status`: si coincide el código o el
      status, devuelve un `BusinessRejection` de duplicado (status de
      rechazo = `rejection_status` o `duplicate_status` si se omite).
    - `not_found_status`: si coincide el status, devuelve un
      `BusinessRejection` de not found.
    - Cualquier otro caso devuelve `PipelineError`.
    """
    if duplicate_kind is not None and duplicate_status is not None and (
        exc.code == duplicate_kind or exc.status_code == duplicate_status
    ):
        status = (
            rejection_status if rejection_status is not None else duplicate_status
        )
        return BusinessRejection(exc.detail, duplicate_kind, status)
    if not_found_status is not None and exc.status_code == not_found_status:
        return BusinessRejection(exc.detail, "NOT_FOUND", not_found_status)
    return PipelineError(exc.detail)
