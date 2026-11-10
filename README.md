# Servicio Orquestador

Microservicio orquestador *stateless* (sin estado) construido con FastAPI siguiendo el patrón MVC clásico. Recibe archivos PDF subidos y coordina una canalización (*pipeline*) de tres etapas (validar → extraer → almacenar) contra microservicios internos mediante HTTP asíncrono (`httpx`), ejecutándose detrás del proxy inverso Traefik. Se registra y descubre automáticamente vía Consul (service discovery), degradando a URL estática de configuración cuando Consul no está disponible.

## Arquitectura (MVC)

- `routers/` - Definiciones de rutas livianas, sin lógica de negocio.
- `controllers/` - Orquestación: el cerebro de la canalización (validar → extraer → almacenar).
- `models/` - Contratos de datos (PDF, PipelineResult, DTOs internos).
- `views/` - Serialización de respuestas (éxito 201/200, errores 400/422/503).
- `services/` - Clientes HTTP para los microservicios internos (`service_clients`) y manejo de errores de upstream (`service_errors`).
- `config.py` - Configuración desde variables de entorno (Pydantic Settings).
- `exceptions.py` - `PipelineError`, `BusinessRejection`, `ServiceError`, `UpstreamError`.
- `main.py` - Aplicación FastAPI (monta routers, registra manejadores de excepciones y wired con Consul).
- `constants.py` - Constantes compartidas (única fuente de verdad).

El servicio es *stateless*: no utiliza base de datos ni caché local. Los reintentos de HTTP son responsabilidad de Traefik, no del cliente (`httpx`).

## Comandos

```sh
cp .env.example .env   # .env es opcional en docker-compose (required: false)
uv sync
uv run uvicorn orchestrator.main:app --reload
uv run pytest
uv run ruff check src/orchestrator
uv run mypy src/orchestrator --exclude tests
```

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Health check (200 `{"status": "healthy", "service": "orchestrator"}`). Usado por Consul y Docker HEALTHCHECK. |
| `POST` | `/api/v1/upload` (multipart file) | Ejecuta la canalización sobre un PDF y devuelve 201 con `{status, id, filename, checksum, message}`. |
| `GET` | `/api/v1/documents` | Lista todos los documentos almacenados (200). |
| `GET` | `/api/v1/documents/{doc_id}` | Devuelve un documento por su id (200). |
| `DELETE` | `/api/v1/documents/{doc_id}` | Elimina un documento (204 si se borró, 404 si no existía). |
| `PATCH` | `/api/v1/documents/{doc_id}` | Actualiza metadatos de un documento (200 si se modificó, 404 si no existía). |
| `GET` | `/health/discovery` | Estado del plano de service discovery (fallback activo por servicio). |

Códigos de error: 400 (validación / documento duplicado), 422 (solicitud inválida), 503 (servicio ascendente/upstream no disponible).

## Docker + Traefik

```sh
docker network create traefik-net
docker compose up -d --build
```

Traefik enruta el servicio utilizando las etiquetas (labels) declaradas en `docker-compose.yml` (ingreso web, regla de host `orchestrator.localhost` / `127.0.0.1`, rate limit, retry y circuit breaker).

El servicio se registra en Consul al iniciar y se desregistra al apagarse (SIGINT/SIGTERM). Ante Consul caído, el pipeline sigue funcionando usando las URLs estáticas de configuración (fallback visible vía `/health/discovery`).
