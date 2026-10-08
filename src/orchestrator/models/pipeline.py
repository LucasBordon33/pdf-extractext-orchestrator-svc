"""Estado de la canalización de subida."""

from enum import Enum, auto


class StageStatus(Enum):
    """Resultado de una etapa de la canalización."""

    SUCCEEDED = auto()
    FAILED = auto()


class PipelineResult:
    """Registro del resultado de cada etapa de la canalización."""

    def __init__(self) -> None:
        self._statuses: dict[str, StageStatus] = {}

    def start_stage(self, name: str) -> str:
        """Devuelve el token de la etapa `name` (el propio nombre)."""
        return name

    def finish_stage(self, stage: str, status: StageStatus) -> None:
        self._statuses[stage] = status

    def stage_status(self, name: str) -> StageStatus:
        return self._statuses[name]

    @property
    def overall(self) -> StageStatus:
        if StageStatus.FAILED in self._statuses.values():
            return StageStatus.FAILED
        return StageStatus.SUCCEEDED

    def finalize(self) -> None:
        """Cierra el resultado; en este modelo no cambia su estado."""
