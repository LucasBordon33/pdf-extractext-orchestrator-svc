"""Health check del orquestador, consumido por Consul y Docker.

Contrato fijado por `tests/test_integration.py`:
`GET /health` -> 200 `{"status": "healthy", "service": "orchestrator"}`.
La implementación vive en el paquete compartido para no duplicar el
endpoint en cada microservicio (DRY).
"""

from fastapi import FastAPI

from orchestrator.infrastructure.service_discovery import add_health_route


def attach_health(app: FastAPI) -> None:
    """Publica `GET /health` con el body contractual del orquestador."""
    add_health_route(app, service_name="orchestrator")
