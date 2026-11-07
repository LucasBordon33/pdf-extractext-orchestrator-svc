"""Fábricas Consul ligadas a la configuración del entorno (composition root).

La configuración proviene de variables de entorno con defaults propios
del servicio (`load_settings`): precedencia `env var > default`.
"""

from functools import lru_cache

from orchestrator.infrastructure.service_discovery import (
    ConsulAgentClient,
    ServiceDiscoverySettings,
    load_settings,
)

_SERVICE_DEFAULTS = {
    "service_name": "orchestrator",
    "service_port": 8000,
    "service_health_path": "/health",
}


@lru_cache(maxsize=1)
def consul_settings() -> ServiceDiscoverySettings:
    """Configuración única de discovery para el proceso."""
    return load_settings(**_SERVICE_DEFAULTS)


@lru_cache(maxsize=1)
def build_consul_client() -> ConsulAgentClient:
    """Cliente HTTP del agente Consul (singleton del proceso)."""
    return ConsulAgentClient(consul_settings())
