"""Descubrimiento dinámico de servicios para el orquestador.

El orquestador es el único servicio que **consume** discovery: resuelve
`validator`, `extractor` y `store` por nombre en lugar de depender de
URLs estáticas. Ante Consul caído o sin instancias saludables, degrada
a la URL estática de `Settings` (config por entorno), de modo que el
pipeline nunca se cae por el plano de discovery.

El fallback es **visible**: cada servicio que cae a URL estática queda
registrado en `_fallback_services` y puede consultarse con
`fallback_active_for(service_name)`.
"""

from functools import lru_cache

from orchestrator.infrastructure.service_discovery import (
    ConsulServiceDiscovery,
    get_logger,
)

from .client import build_consul_client, consul_settings

logger = get_logger()

# Servicios que actualmente están usando URL estática (fallback) porque
# Consul no respondió o no devolvió instancias saludables.
_fallback_services: set[str] = set()


@lru_cache(maxsize=1)
def build_discovery() -> ConsulServiceDiscovery:
    """Instancia única del descubridor (caché TTL compartida)."""
    return ConsulServiceDiscovery(build_consul_client(), consul_settings())


def fallback_active_for(service_name: str) -> bool:
    """Devuelve `True` si `service_name` está usando URL estática (fallback).

    Útil para observabilidad y health-checks del plano de discovery.
    """
    return service_name in _fallback_services


def fallback_services() -> frozenset[str]:
    """Devuelve copia inmutable de los servicios actualmente en fallback."""
    return frozenset(_fallback_services)


def resolve_url(service_name: str, fallback: str) -> str:
    """URL base de una instancia saludable o `fallback` estático.

    Nunca lanza: una indisponibilidad de Consul no debe tumbar requests
    del pipeline (degradación controlada). El resultado negativo queda
    cacheado por TTL, así que el costo ante caída es una llamada por
    ventana, no una por request.

    Cuando se usa `fallback`, el servicio queda registrado como en
    fallback para poder consultarse con `fallback_active_for`.
    """
    if not consul_settings().service_discovery_enabled:
        _fallback_services.add(service_name)
        logger.info(
            "Discovery deshabilitado; se usa URL estática",
            extra={
                "event": "discovery_disabled",
                "service": service_name,
                "fallback": fallback,
                "fallback_active": True,
            },
        )
        return fallback
    try:
        instance = build_discovery().discover(service_name)
    except Exception:  # noqa: BLE001 - el discovery no puede romper requests
        _fallback_services.add(service_name)
        logger.warning(
            "Error inesperado en discovery; se usa URL estática (fallback activo)",
            extra={
                "event": "discovery_unexpected_error",
                "service": service_name,
                "fallback": fallback,
                "fallback_active": True,
            },
        )
        return fallback
    if instance is None:
        _fallback_services.add(service_name)
        logger.info(
            "Sin instancias saludables en Consul; se usa URL estática (fallback activo)",
            extra={
                "event": "discovery_empty",
                "service": service_name,
                "fallback": fallback,
                "fallback_active": True,
            },
        )
        return fallback
    # Si había fallado antes y ahora se recuperó, quitar del registro de fallback
    _fallback_services.discard(service_name)
    logger.debug(
        "Discovery resuelto por Consul",
        extra={
            "event": "discovery_resolved",
            "service": service_name,
            "url": instance.base_url,
            "fallback_active": False,
        },
    )
    return instance.base_url
