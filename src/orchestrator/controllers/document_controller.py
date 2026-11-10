"""Controlador de consulta de documentos almacenados en el store (MS4)."""

from typing import Any, Protocol

from orchestrator.exceptions import ServiceError
from orchestrator.models.pdf import PDF
from orchestrator.services.service_errors import handle_service_errors, map_store_error


class StoreReadPort(Protocol):
    """Consulta de documentos persistidos."""

    def get_by_id(self, doc_id: str) -> dict[str, Any]: ...

    def list_all(self) -> list[dict[str, Any]]: ...

    def delete_by_id(self, doc_id: str) -> bool: ...

    def update_by_id(
        self, doc_id: str, name: str | None = None, text: str | None = None, size: int | None = None
    ) -> dict[str, Any] | None: ...


def _rejection_from_store(exc: ServiceError) -> Exception:
    return map_store_error(exc, not_found_status=404)


class DocumentController:
    """Recupera documentos del store sin conocer HTTP ni URLs."""

    def __init__(self, store: StoreReadPort) -> None:
        self._store = store

    def get_document(self, doc_id: str) -> PDF:
        payload = handle_service_errors(
            lambda: self._store.get_by_id(doc_id),
            _rejection_from_store,
        )
        return _to_pdf(payload)

    def list_documents(self) -> list[PDF]:
        payloads = handle_service_errors(
            lambda: self._store.list_all(),
            _rejection_from_store,
        )
        return [_to_pdf(payload) for payload in payloads]

    def delete_document(self, doc_id: str) -> bool:
        return handle_service_errors(
            lambda: self._store.delete_by_id(doc_id),
            _rejection_from_store,
        )

    def update_document(
        self,
        doc_id: str,
        name: str | None = None,
        text: str | None = None,
        size: int | None = None,
    ) -> PDF | None:
        payload = handle_service_errors(
            lambda: self._store.update_by_id(doc_id, name=name, text=text, size=size),
            _rejection_from_store,
        )
        if payload is None:
            return None
        return _to_pdf(payload)


def _to_pdf(payload: dict[str, Any]) -> PDF:
    return PDF(
        id=str(payload["id"]),
        name=str(payload["name"]),
        text=str(payload["content"]),
        checksum=str(payload["checksum"]),
        size=int(payload.get("size", 0)),
        created_at=payload.get("created_at"),
    )
