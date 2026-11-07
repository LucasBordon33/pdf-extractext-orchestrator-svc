"""Integración Consul del orquestador.

Solo composición: la implementación vive en el paquete compartido
`orchestrator.infrastructure.service_discovery` (vendored). Este paquete
liga la identidad del servicio con el entorno y expone los puntos de
integración que consume `main.py`.
"""

from .discovery import build_discovery, resolve_url
from .health import attach_health
from .lifecycle import attach_lifespan
from .registry import build_registry

__all__ = [
    "attach_health",
    "attach_lifespan",
    "build_discovery",
    "build_registry",
    "resolve_url",
]
