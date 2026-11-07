"""Registro del orquestador en Consul (adaptador de `IServiceRegistry`)."""

from functools import lru_cache

from orchestrator.infrastructure.service_discovery import ConsulServiceRegistry

from .client import build_consul_client, consul_settings


@lru_cache(maxsize=1)
def build_registry() -> ConsulServiceRegistry:
    """Instancia única del registro para el proceso."""
    return ConsulServiceRegistry(build_consul_client(), consul_settings())
