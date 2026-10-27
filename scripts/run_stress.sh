#!/usr/bin/env bash
# =============================================================================
# Orquestador de pruebas de carga (Issue 33) — Microservicio 1 (Orquestador)
#
# Pipeline:
#   1. Estado conocido: `docker compose down -v` + `up --build -d`
#   2. Espera hasta que el servicio esté healthy
#   3. Test de spike (k6) con export del resumen a JSON
#   4. Carga fija (Vegeta) via src/orchestrator/tests/stress/vegeta_load.sh
#   5. Comparador: python src/orchestrator/tests/stress/compare.py
#
# Uso:  bash scripts/run_stress.sh
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
RESULTS_DIR="src/orchestrator/tests/stress/results"
PDF_FILES="${PDF_FILES:-prueba.pdf}"
READY_ATTEMPTS="${READY_ATTEMPTS:-60}"

mkdir -p "$RESULTS_DIR"

echo "== Reset del stack: down -v =="
docker compose down -v
echo "== Rebuild y levantado: up --build -d =="
docker compose up --build -d

echo "== Warm-up inicial (sleep 10) =="
sleep 10
echo "== Esperando servicio healthy en $BASE_URL/health (max ${READY_ATTEMPTS}s) =="
ready=0
for i in $(seq 1 "$READY_ATTEMPTS"); do
  health_ok=$(curl -fs -o /dev/null -w "%{http_code}" "$BASE_URL/health" || true)
  if [ "$health_ok" = "200" ]; then
    ready=1
    echo "   listo tras ${i}s extra: proxy 200"
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "ERROR: el servicio no quedó healthy a tiempo" >&2
  docker compose ps
  exit 1
fi

echo "== k6: spike 100 VUs =="
k6_code=0
k6 run -e BASE_URL="$BASE_URL" -e UPLOAD_PATH=/api/v1/upload -e PDF_FILES="$PDF_FILES" \
  --summary-export="$RESULTS_DIR/k6_summary.json" \
  src/orchestrator/tests/stress/spike.js || k6_code=$?
echo "   k6 exit code: $k6_code"

echo "== Vegeta: carga fija 50 req/s =="
BASE_URL="$BASE_URL" bash src/orchestrator/tests/stress/vegeta_load.sh

echo "== Comparador de resultados =="
uv run python src/orchestrator/tests/stress/compare.py
exit_code=$?
echo "== Orquestador finalizado (exit $exit_code) =="
exit $exit_code
