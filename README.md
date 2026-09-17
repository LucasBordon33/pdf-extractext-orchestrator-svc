# Servicio Orquestador

Microservicio orquestador *stateless* (sin estado) construido con FastAPI siguiendo el patrón MVC clásico. Recibe archivos PDF subidos y coordina una canalización (*pipeline*) de tres etapas contra microservicios internos mediante HTTP asíncrono (`httpx`), ejecutándose detrás del proxy inverso Traefik.

## Arquitectura (MVC)

- `routers/` - Definiciones de rutas livianas, sin lógica de negocio.
- `controllers/` - Orquestación: el cerebro de la canalización (validar → extraer → almacenar).
- `models/` - Contratos de datos (PDF, PipelineResult, DTOs internos).
- `views/` - Serialización de respuestas (éxito 201/200, errores 400/422/503).
- `services/` - Clientes HTTP para los microservicios internos (reintentos/*backoff*).
- `config.py` - Configuración desde variables de entorno (Pydantic Settings).
- `exceptions.py` - `PipelineError`, `BusinessRejection`, `ServiceError`.
- `main.py` - Aplicación FastAPI (monta routers, registra manejadores de excepciones).

El servicio es *stateless*: no utiliza base de datos ni caché local.

## Comandos

```sh
cp .env.example .env
uv sync
uv run uvicorn orchestrator.main:app --reload
uv run pytest
uv run ruff check src/orchestrator
uv run mypy src/orchestrator --exclude tests

## Endpoints
POST /api/v1/uploads (multipart file) - Ejecuta la canalización sobre un PDF y devuelve 201 con {status, id, filename, checksum, message}.

Códigos de error: 400 (validación / documento duplicado), 422 (solicitud inválida), 503 (servicio ascendente/upstream no disponible).

## Docker + Traefik

docker network create traefik-net
docker compose up -d --build

Traefik enruta el servicio utilizando las etiquetas (labels) declaradas en docker-compose.yml (ingreso web, regla de host orchestrator.localhost).
