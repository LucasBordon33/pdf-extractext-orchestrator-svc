// Smoke de carga para CI (NO es la prueba de stress del TP):
// 1 VU durante 10 s contra POST /api/v1/upload. Verifica que el contrato
// {status, id, filename, checksum} se sostiene bajo concurrencia baja.
//
// NOTA: Traefik aplica rate limit (10 req/s, burst 25) y circuit breaker.
// Este script usa 1 VU + sleep(1) entre peticiones para no saturar esos
// patrones de resiliencia. Si necesitas más carga, ajusta VUS y sleep en
// consecuencia.
//
// Uso local: k6 run -e BASE_URL=https://universidad.localhost:443 load/k6-smoke.js
//
// Si Traefik usa un certificado autofirmado, forzar:
//   K6_INSECURE_SKIP_TLS_VERIFY=true k6 run -e BASE_URL=https://universidad.localhost:443 load/k6-smoke.js

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: parseInt(__ENV.VUS || "1"),
  duration: "10s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<30000"],
  },
};

const pdfFile = open('../src/orchestrator/tests/stress/pdfs/prueba.pdf', 'b');

const BASE_URL = __ENV.BASE_URL || "https://localhost:443";

http.setResponseCallback(http.expectedStatuses({ min: 200, max: 400 }));

export default function () {
  const response = http.post(`${BASE_URL}/api/v1/upload`, {
    file: http.file(pdfFile, "prueba.pdf", "application/pdf"),
  }, {
    headers: {},
    timeout: "30s",
  });

  check(response, {
    "status 201 o 400 (duplicado)": (r) => r.status === 201 || r.status === 400,
    "contrato valido": (r) => {
      if (r.status === 201) {
        const body = r.json();
        return (
          body.status === "success" &&
          typeof body.id === "string" && body.id.length > 0 &&
          typeof body.filename === "string" && body.filename.length > 0 &&
          typeof body.checksum === "string" && body.checksum.length > 0
        );
      }
      if (r.status === 400) {
        try {
          return typeof r.json('detail') === 'string' && r.json('detail').includes('already exists');
        } catch (e) {
          return false;
        }
      }
      return false;
    },
  });

  // sleep para no saturar el rate limit de Traefik (10 req/s, burst 25)
  sleep(5);
}
