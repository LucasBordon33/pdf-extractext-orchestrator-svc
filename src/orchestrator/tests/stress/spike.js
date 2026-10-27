/**
 * Issue 31 — Test de Spike (k6) — Microservicio 1 (Orquestador)
 * ------------------------------
 * Escenario: 0 -> 100 VUs en 10 s, sostener 100 VUs por 20 s, bajar a 0 en 10 s.
 * Mide el comportamiento del orquestador bajo una subida abrupta de carga.
 *
 * Endpoint MS1: POST /api/v1/upload (multipart, campo "file").
 *
 * Ejecucion:
 *   k6 run src/orchestrator/tests/stress/spike.js
 *   k6 run -e BASE_URL=http://localhost:8000 -e MAX_P95=9000 src/orchestrator/tests/stress/spike.js
 */

import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const UPLOAD_PATH = __ENV.UPLOAD_PATH || '/api/v1/upload';

export const options = {
  stages: [
    { duration: '10s', target: 100 },
    { duration: '20s', target: 100 },
    { duration: '10s', target: 0 },
  ],
  discardResponseBodies: false,
  summaryTrendStats: ['min', 'avg', 'p(50)', 'p(90)', 'p(95)', 'max', 'count'],
  thresholds: {
    http_req_failed: ['rate==0'],
    checks: ['rate>0.99'],
    http_req_duration: [
      `p(50)<${__ENV.MAX_P50 || 1880}`,
      `p(90)<${__ENV.MAX_P90 || 7830}`,
      `p(95)<${__ENV.MAX_P95 || 8800}`,
      `max<${__ENV.MAX_MAX || 13940}`,
    ],
  },
};

// Validacion de contrato: 201 (subida ok) y 400 (duplicado por checksum) son
// respuestas validas del negocio; ninguno cuenta como fallo de HTTP.
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 400 }));

const raw_pdf_files = __ENV.PDF_FILES || 'prueba.pdf';
const pdf_names = raw_pdf_files.split(',');
const PDF_FILES = [];
for (let i = 0; i < pdf_names.length; i++) {
  const name = pdf_names[i].trim();
  if (name.length > 0) {
    PDF_FILES.push(name);
  }
}

const documents = [];
for (let i = 0; i < PDF_FILES.length; i++) {
  const name = PDF_FILES[i];
  const bytes = open(`pdfs/${name}`, 'b');
  documents.push({ name, bytes });
}

export default function () {
  const doc = documents[Math.floor(Math.random() * documents.length)];

  const res = http.post(
    `${BASE_URL}${UPLOAD_PATH}`,
    {
      file: http.file(doc.bytes, doc.name, 'application/pdf'),
    },
    { tags: { name: 'spike-upload' } }
  );

  check(res, {
    'status es 201 o 400 (duplicado)': (r) => r.status === 201 || r.status === 400,
    'respuesta tiene id o mensaje de duplicado': (r) => {
      try {
        const body = r.json();
        return (
          (r.status === 201 && typeof body.id === 'string' && body.id.length > 0) ||
          (r.status === 400 && typeof body.detail === 'string' && body.detail.includes('already exists'))
        );
      } catch (e) {
        return false;
      }
    },
    'respuesta tiene filename (si 201)': (r) => {
      if (r.status !== 201) return true;
      try {
        return typeof r.json('filename') === 'string' && r.json('filename').length > 0;
      } catch (e) {
        return false;
      }
    },
    'respuesta tiene checksum (si 201)': (r) => {
      if (r.status !== 201) return true;
      try {
        return typeof r.json('checksum') === 'string' && r.json('checksum').length > 0;
      } catch (e) {
        return false;
      }
    },
    'estado success (si 201)': (r) => {
      if (r.status !== 201) return true;
      try {
        return r.json('status') === 'success';
      } catch (e) {
        return false;
      }
    },
  });
}
