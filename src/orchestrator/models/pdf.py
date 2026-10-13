"""Entidad del documento PDF procesado."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PDF:
    """Documento al final de la canalización o recuperado del store.

    `name` es el nombre saneado, `text` el markdown extraído,
    `checksum` el sha256 hex del contenido e `id` el asignado por el store.
    `size` y `created_at` solo se completan cuando el documento proviene del
    store (MS4); en el alta quedan con sus valores por defecto.
    """

    id: str
    name: str
    text: str
    checksum: str
    size: int = 0
    created_at: str | None = None
