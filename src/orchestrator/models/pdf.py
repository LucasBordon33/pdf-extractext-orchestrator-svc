"""Entidad del documento PDF procesado."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PDF:
    """Documento al final de la canalización.

    `name` es el nombre saneado, `text` el markdown extraído,
    `checksum` el sha256 hex del contenido e `id` el asignado por el store.
    """

    id: str
    name: str
    text: str
    checksum: str
