"""Controlador de consulta de documentos almacenados en el store (MS4)."""

from typing import Any, Protocol

from orchestrator.exceptions import BusinessRejection, PipelineError, ServiceError, UpstreamError
from orchestrator.models.pdf import PDF


class StoreReadPort(Protocol):
    """Consulta de documentos persistidos."""

    def get_by_id(self, doc_id: str) -> dict[str, Any]: ...

    def list_all(self) -> list[dict[str, Any]]: ...


def _rejection_from_store(exc: ServiceError) -> Exception:
    if exc.status_code == 404:
        return BusinessRejection(exc.detail, "NOT_FOUND", 404)
    return PipelineError(exc.detail)


class DocumentController:
    """Recupera documentos del store sin conocer HTTP ni URLs."""

    def __init__(self, store: StoreReadPort) -> None:
        self._store = store

    def get_document(self, doc_id: str) -> PDF:
        try:
            payload = self._store.get_by_id(doc_id)
        except UpstreamError:
            raise
        except ServiceError as exc:
            raise _rejection_from_store(exc) from exc
        return _to_pdf(payload)

    def list_documents(self) -> list[PDF]:
        try:
            payloads = self._store.list_all()
        except UpstreamError:
            raise
        except ServiceError as exc:
            raise _rejection_from_store(exc) from exc
        return [_to_pdf(payload) for payload in payloads]


def _to_pdf(payload: dict[str, Any]) -> PDF:
    return PDF(
        id=str(payload["id"]),
        name=str(payload["name"]),
        text=str(payload["content"]),
        checksum=str(payload["checksum"]),
        size=int(payload.get("size", 0)),
        created_at=payload.get("created_at"),
    )
