#!/usr/bin/env bash
# =============================================================================
# Prueba de carga fija con Vegeta (Open Model) — Microservicio 1 (Orquestador)
# -----------------------------------------------------------------------------
# 50 req/s fijos durante 30 s contra http://localhost:8000/api/v1/upload.
#
# MS1 espera multipart/form-data con campo "file" (FastAPI UploadFile).
# Vegeta acepta un solo -body por proceso, por lo que se lanzan 4 ataques en
# paralelo (12.5 req/s cada uno => 50 req/s agregado), cada uno con un PDF
# distinto embargado en un target multipart generado al vuelo.
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
RATE="25/2s"
DURATION="${DURATION:-30s}"
TIMEOUT="${TIMEOUT:-30s}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
PDFS_DIR="$SCRIPT_DIR/pdfs"

mkdir -p "$RESULTS_DIR"
rm -f "$RESULTS_DIR"/res*.bin "$RESULTS_DIR"/target_*.txt "$RESULTS_DIR"/reporte_crudo.bin

echo "== Vegeta: Open Model ${DURATION} a 50 req/s contra $BASE_URL/api/v1/upload =="

for i in 1 2 3 4; do
  TARGET="$RESULTS_DIR/target_$i.txt"
  BOUNDARY="----FormBoundary$(date +%s)$$${i}"
  {
    printf 'POST %s/api/v1/upload\r\n' "$BASE_URL"
    printf 'Content-Type: multipart/form-data; boundary=%s\r\n' "$BOUNDARY"
    printf '\r\n'
    printf -- '--%s\r\n' "$BOUNDARY"
    printf 'Content-Disposition: form-data; name="file"; filename="%s.pdf"\r\n' "$i"
    printf 'Content-Type: application/pdf\r\n'
    printf '\r\n'
    cat "$PDFS_DIR/$i.pdf"
    printf '\r\n'
    printf -- '--%s--\r\n' "$BOUNDARY"
  } > "$TARGET"

  cat "$TARGET" | vegeta attack \
    -rate="$RATE" \
    -duration="$DURATION" \
    -timeout="$TIMEOUT" \
    > "$RESULTS_DIR/res$i.bin" &
done

wait

vegeta report "$RESULTS_DIR"/res*.bin | tee "$RESULTS_DIR/reporte.txt"
vegeta report -type=json "$RESULTS_DIR"/res*.bin > "$RESULTS_DIR/reporte.json"

cat <<'EOF'

## Prueba de carga fija con Vegeta (`src/orchestrator/tests/stress/vegeta_load.sh`)

**Carga en Modelo Abierto de 50 req/s durante 30 s contra el orquestador (POST /api/v1/upload).**

### Rotación de archivos

Vegeta acepta un único `-body` por proceso, por lo que no puede rotar
archivos dentro de un mismo ataque. La rotación de los 4 PDFs se resolvió
dividiendo la carga en 4 procesos `vegeta attack` concurrentes, cada uno con
un PDF distinto (`1.pdf` ... `4.pdf`) con una tasa de 25 req cada 2s:
(25/2) x 4 = 50 req/s de tráfico agregado.

Cada ataque se construye como un target multipart/form-data con el PDF binario
embargado, ya que MS1 espera `UploadFile` (multipart), no body crudo.

### Salidas en `src/orchestrator/tests/stress/results/`

| Archivo | Contenido |
|---|---|
| `target_1..4.txt` | Targets multipart generados por ataque |
| `res1..4.bin` | Resultados crudos por ataque (formato gob de Vegeta) |
| `reporte.txt` | Reporte de texto: p50/p90/p95/p99 y status codes |
| `reporte.json` | Mismo reporte en JSON para el comparador |

### Uso

```bash
bash src/orchestrator/tests/stress/vegeta_load.sh
```

EOF
