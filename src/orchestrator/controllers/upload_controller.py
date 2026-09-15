import hashlib
from pathlib import Path
from typing import Any, Protocol

from orchestrator.exceptions import BusinessRejection, PipelineError, ServiceError
from orchestrator.models.pdf import PDF
from orchestrator.models.pipeline import PipelineResult, StageStatus


class ValidatorPort(Protocol):
    async def validate(self, data: dict[str, Any]) -> dict[str, Any]: ...


class ExtractorPort(Protocol):
    async def extract(self, data: dict[str, Any]) -> dict[str, Any]: ...


class StorePort(Protocol):
    async def store(self, data: dict[str, Any]) -> dict[str, Any]: ...


class UploadController:
    def __init__(
        self, validator: ValidatorPort, extractor: ExtractorPort, store: StorePort
    ) -> None:
        self._validator = validator
        self._extractor = extractor
        self._store = store

    async def handle_upload(self, filename: str, content: bytes) -> tuple[PDF, PipelineResult]:
        checksum = hashlib.sha256(content).hexdigest()
        name = Path(filename).name
        size = len(content)
        result = PipelineResult()

        # Stage 1: Validate
        stage = result.start_stage("validate")
        try:
            payload = {"name": name, "size": size, "checksum": checksum}
            validation = await self._validator.validate(payload)
        except ServiceError as exc:
            result.finish_stage(stage, StageStatus.FAILED)
            if exc.status_code == 400:
                raise BusinessRejection(str(exc.detail), kind="VALIDATION_ERROR") from exc
            raise PipelineError(str(exc.detail)) from exc
        if not validation.get("valid", False):
            result.finish_stage(stage, StageStatus.FAILED)
            reason = validation.get("reason", "Document failed validation")
            raise BusinessRejection(reason, kind="VALIDATION_ERROR")
        result.finish_stage(stage, StageStatus.SUCCEEDED)

        # Stage 2: Extract
        stage = result.start_stage("extract")
        try:
            payload = {"name": name, "checksum": checksum}
            extraction = await self._extractor.extract(payload)
        except ServiceError as exc:
            result.finish_stage(stage, StageStatus.FAILED)
            if exc.status_code == 400:
                raise BusinessRejection(str(exc.detail), kind="EXTRACTION_ERROR") from exc
            raise PipelineError(str(exc.detail)) from exc
        result.finish_stage(stage, StageStatus.SUCCEEDED)
        text = extraction.get("text", "")

        # Stage 3: Store
        stage = result.start_stage("store")
        try:
            payload = {"name": name, "text": text, "checksum": checksum}
            store_resp = await self._store.store(payload)
        except ServiceError as exc:
            result.finish_stage(stage, StageStatus.FAILED)
            if exc.status_code == 409:
                msg = "Document already exists"
                raise BusinessRejection(msg, kind="DUPLICATE_DOCUMENT") from exc
            raise PipelineError(str(exc.detail)) from exc
        result.finish_stage(stage, StageStatus.SUCCEEDED)

        result.finalize()
        pdf = PDF(
            id=store_resp.get("id", ""),
            name=name,
            text=text,
            checksum=checksum,
        )
        return pdf, result