// Smoke de carga para CI (NO es la prueba de stress del TP):
// 10 VUs durante 10 s contra POST /api/v1/upload. Verifica que el contrato
// {status, id, filename, checksum} se sostiene bajo concurrencia.
//
// Uso local: k6 run -e BASE_URL=http://localhost:8000 load/k6-smoke.js

import http from "k6/http";
import { check } from "k6";

export const options = {
  vus: 10,
  duration: "10s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<30000"],
  },
};

const pdf = open("src/orchestrator/tests/stress/pdfs/prueba.pdf", "b");

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const response = http.post(`${BASE_URL}/api/v1/upload`, {
    file: http.file(pdf, "prueba.pdf", "application/pdf"),
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
}
