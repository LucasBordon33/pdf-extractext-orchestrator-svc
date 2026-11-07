"""Descubrimiento dinámico de servicios para el orquestador.

El orquestador es el único servicio que **consume** discovery: resuelve
`validator`, `extractor` y `store` por nombre en lugar de depender de
URLs estáticas. Ante Consul caído o sin instancias saludables, degrada
a la URL estática de `Settings` (config por entorno), de modo que el
pipeline nunca se cae por el plano de discovery.
"""

from functools import lru_cache

from orchestrator.infrastructure.service_discovery import (
    ConsulServiceDiscovery,
    get_logger,
)

from .client import build_consul_client, consul_settings

logger = get_logger()


@lru_cache(maxsize=1)
def build_discovery() -> ConsulServiceDiscovery:
    """Instancia única del descubridor (caché TTL compartida)."""
    return ConsulServiceDiscovery(build_consul_client(), consul_settings())


def resolve_url(service_name: str, fallback: str) -> str:
    """URL base de una instancia saludable o `fallback` estático.

    Nunca lanza: una indisponibilidad de Consul no debe tumbar requests
    del pipeline (degradación controlada). El resultado negativo queda
    cacheado por TTL, así que el costo ante caída es una llamada por
    ventana, no una por request.
    """
    if not consul_settings().service_discovery_enabled:
        return fallback
    try:
        instance = build_discovery().discover(service_name)
    except Exception:  # noqa: BLE001 - el discovery no puede romper requests
        logger.warning(
            "Error inesperado en discovery; se usa URL estática",
            extra={"event": "discovery_unexpected_error", "service": service_name},
        )
        return fallback
    if instance is None:
        logger.info(
            "Sin instancias saludables en Consul; se usa URL estática",
            extra={"event": "discovery_empty", "service": service_name},
        )
        return fallback
    return instance.base_url
