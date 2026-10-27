# syntax=docker/dockerfile:1

# ============================================================
# Stage 1 (build): resuelve e instala las dependencias con uv
# ============================================================
# Variante con Python 3.12 preinstalado sobre bookworm-slim: usa el mismo
# layout de intérprete que el stage de runtime (/usr/local/bin/python3.12),
# para que los symlinks del .venv copiado sigan resolviendo.
# ============================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

WORKDIR /app

# Manifiestos primero: esta capa se cachea mientras no cambien. README.md es
# necesario porque pyproject.toml lo declara y hatchling lo valida al construir.
COPY pyproject.toml uv.lock README.md ./

# El proyecto es instalable (hatchling), así que `uv sync` también lo construye
# e instala como editable: necesita el paquete fuente disponible.
COPY src ./src

# Fuerza el uso del Python 3.12 preinstalado en la imagen; si uv descargara
# uno propio, sus binarios no existirían en el stage de runtime.
ENV UV_PYTHON_DOWNLOADS=never

# Instala exactamente lo que declara uv.lock, sin el grupo dev.
RUN uv sync --frozen --no-dev

# ============================================================
# Stage 2 (runtime): imagen final de producción, solo la app
# ============================================================
# Sin k6 ni vegeta: son herramientas de desarrollo/pruebas de carga.
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Entorno virtual ya resuelto: dependencias listas para usar.
COPY --from=build /app/.venv /app/.venv

# Código de la aplicación (la instalación editable apunta a /app/src).
COPY src ./src

# Binarios del venv por defecto: `uvicorn` resuelve al del venv.
ENV PATH="/app/.venv/bin:$PATH"

# Logs de uvicorn/FastAPI sin buffering (salida directa a consola).
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]

