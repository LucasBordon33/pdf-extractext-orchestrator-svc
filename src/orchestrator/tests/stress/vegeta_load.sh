#!/usr/bin/env bash
# =============================================================================
# Prueba de carga fija con Vegeta (Open Model) — Microservicio 1 (Orquestador)
# -----------------------------------------------------------------------------
# 5 req/s fijos durante 30 s contra https://localhost:443/health.
#
# Vegeta lee targets desde stdin: "METHOD URL" por línea.
# Este script se limita a verificar que el health check responde bajo carga
# a través de Traefik (TLS, puerto 443).
#
# Se lanza un solo ataque a 5 req/s (por debajo del rate limit de Traefik:
# 10 req/s, burst 25).
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost:443}"
RATE="5"
DURATION="${DURATION:-30s}"
TIMEOUT="${TIMEOUT:-30s}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"

mkdir -p "$RESULTS_DIR"
rm -f "$RESULTS_DIR"/res*.bin "$RESULTS_DIR"/target_*.txt "$RESULTS_DIR"/reporte_crudo.bin

echo "== Vegeta: Open Model ${DURATION} a ${RATE} req/s contra ${BASE_URL}/health =="

echo "GET ${BASE_URL%/}/health" | vegeta attack \
    -rate="$RATE" \
    -duration="$DURATION" \
    -timeout="$TIMEOUT" \
    -insecure \
    > "$RESULTS_DIR/res1.bin"

vegeta report "$RESULTS_DIR"/res1.bin | tee "$RESULTS_DIR/reporte.txt"
vegeta report -type=json "$RESULTS_DIR"/res1.bin > "$RESULTS_DIR/reporte.json"

cat <<'EOF'

## Prueba de carga fija con Vegeta (`src/orchestrator/tests/stress/vegeta_load.sh`)

**Carga en Modelo Abierto de 5 req/s durante 30 s contra el health check del orquestador (GET /health).**

### Alcance

Vegeta no genera targets multipart dinámicos de forma confiable desde bash, por
este script se limita a verificar que el health check responde bajo carga a través
de Traefik (TLS, puerto 443). Para pruebas de upload real con PDF multipart usar
`k6 run load/k6-smoke.js`.

El rate está fijado en 5 req/s para mantenerse por debajo del rate limit de
Traefik (10 req/s, burst 25).

### Salidas en `src/orchestrator/tests/stress/results/`

| Archivo | Contenido |
|---|---|
| `res1.bin` | Resultado crudo del ataque (formato gob de Vegeta) |
| `reporte.txt` | Reporte de texto: p50/p90/p95/p99 y status codes |
| `reporte.json` | Mismo reporte en JSON para el comparador |

### Uso

```bash
export BASE_URL=https://universidad.localhost:443
bash src/orchestrator/tests/stress/vegeta_load.sh
EOF

