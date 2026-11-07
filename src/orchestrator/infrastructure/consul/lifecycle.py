"""Ciclo de vida de registro en Consul para la app del orquestador.

- Al iniciar la app (lifespan startup): registro automático.
- Al apagar (SIGINT/SIGTERM -> shutdown de uvicorn): desregistro
  automático, evitando registros huérfanos. Ante SIGKILL, Consul purga
  la instancia vía `DeregisterCriticalServiceAfter` (60s por defecto).
"""

from fastapi import FastAPI

from orchestrator.infrastructure.service_discovery import attach_consul_lifespan

from .registry import build_registry


def attach_lifespan(app: FastAPI) -> None:
    """Acopla registro/desregistro al lifespan existente de la app."""
    attach_consul_lifespan(app, build_registry())
