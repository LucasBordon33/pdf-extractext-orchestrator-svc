"""Controlador de la canalización de subida: valida, extrae y almacena en orden estricto."""

import hashlib
from pathlib import Path
from typing import Any, Protocol

from orchestrator.config import Settings
from orchestrator.exceptions import (
    BusinessRejection,
    PipelineError,
    ServiceError,
    UpstreamError,
)
from orchestrator.models.pdf import PDF
from orchestrator.models.pipeline import PipelineResult, StageStatus

OVERSIZE_DETAIL = "El archivo excede el tamaño permitido"

_VALIDATE_STAGE = "validate"
_EXTRACT_STAGE = "extract"
_STORE_STAGE = "store"


class ValidatorPort(Protocol):
    """Etapa 1: valida el PDF."""

    def validate(self, content: bytes, filename: str) -> dict[str, Any]: ...


class ExtractorPort(Protocol):
    """Etapa 2: extrae el texto del PDF."""

    def extract(self, content: bytes, filename: str) -> dict[str, Any]: ...


class StorePort(Protocol):
    """Etapa 3: persiste el PDF."""

    def store(self, name: str, text: str, checksum: str, size: int = 0) -> dict[str, Any]: ...


def _rejection_from_validator(exc: ServiceError) -> Exception:
    if exc.status_code < 500:
        return BusinessRejection(exc.detail, "VALIDATION_ERROR", exc.status_code)
    return PipelineError(exc.detail)


def _rejection_from_extractor(exc: ServiceError) -> Exception:
    if exc.status_code in (400, 415, 422):
        return BusinessRejection(exc.detail, "EXTRACTION_ERROR", exc.status_code)
    if exc.status_code == 413:
        return BusinessRejection(exc.detail, "VALIDATION_ERROR", 400)
    if exc.status_code == 429:
        return UpstreamError(exc.detail)
    return PipelineError(exc.detail)


def _rejection_from_store(exc: ServiceError) -> Exception:
    if exc.code == "DUPLICATE_DOCUMENT" or exc.status_code == 409:
        return BusinessRejection(exc.detail, "DUPLICATE_DOCUMENT", 400)
    return PipelineError(exc.detail)


class UploadController:
    """Orquesta validar → extraer → almacenar sin conocer HTTP ni URLs."""

    def __init__(
        self,
        validator: ValidatorPort,
        extractor: ExtractorPort,
        store: StorePort,
        settings: Settings,
    ) -> None:
        self._validator = validator
        self._extractor = extractor
        self._store = store
        self._settings = settings

    def handle_upload(self, filename: str, content: bytes) -> tuple[PDF, PipelineResult]:
        name = Path(filename).name
        checksum = hashlib.sha256(content).hexdigest()
        self._reject_oversize(content)

        result = PipelineResult()
        self._run_validate(content, name, result)
        text = self._run_extract(content, name, result)
        stored = self._run_store(name, text, checksum, len(content), result)
        result.finalize()
        return PDF(id=stored["id"], name=name, text=text, checksum=checksum), result

    def _reject_oversize(self, content: bytes) -> None:
        if len(content) > self._settings.max_upload_size:
            raise BusinessRejection(OVERSIZE_DETAIL, "VALIDATION_ERROR", 400)

    def _run_validate(self, content: bytes, name: str, result: PipelineResult) -> None:
        stage = result.start_stage(_VALIDATE_STAGE)
        try:
            outcome = self._validator.validate(content, name)
        except UpstreamError:
            raise
        except ServiceError as exc:
            raise _rejection_from_validator(exc) from exc
        if not outcome.get("valid", False):
            raise BusinessRejection(str(outcome.get("reason", "")), "VALIDATION_ERROR", 400)
        result.finish_stage(stage, StageStatus.SUCCEEDED)

    def _run_extract(self, content: bytes, name: str, result: PipelineResult) -> str:
        stage = result.start_stage(_EXTRACT_STAGE)
        try:
            payload = self._extractor.extract(content, name)
        except UpstreamError:
            raise
        except ServiceError as exc:
            raise _rejection_from_extractor(exc) from exc
        result.finish_stage(stage, StageStatus.SUCCEEDED)
        return str(payload["content"])

    def _run_store(
        self, name: str, text: str, checksum: str, size: int, result: PipelineResult
    ) -> dict[str, Any]:
        stage = result.start_stage(_STORE_STAGE)
        try:
            stored = self._store.store(name, text, checksum, size)
        except UpstreamError:
            raise
        except ServiceError as exc:
            raise _rejection_from_store(exc) from exc
        result.finish_stage(stage, StageStatus.SUCCEEDED)
        return stored
