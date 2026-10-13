import hashlib

from orchestrator.config import Settings

DEFAULT_CONTENT = b"%PDF-1.4 hola contenido"
DEFAULT_CHECKSUM = hashlib.sha256(DEFAULT_CONTENT).hexdigest()

VALIDATOR_400_EXT = "Solo se permiten archivos PDF"
VALIDATOR_400_HEADER = "El archivo no es un PDF válido"
OVERSIZE_MSG = "El archivo excede el tamaño permitido"
EXTRACTION_422 = "No se pudo leer el archivo como PDF"
REPEATED_MSG = "El PDF ya se encuentra repetido en la base de datos."
NOT_FOUND_MSG = "Documento no encontrado"
UPLOAD_OK_MSG = "PDF subido correctamente"

DUPLICATE_CODE = "DUPLICATE_DOCUMENT"

DOCUMENT_ID = "abc123"
DOCUMENT_PAYLOAD = {
    "id": DOCUMENT_ID,
    "name": "doc.pdf",
    "checksum": DEFAULT_CHECKSUM,
    "content": "texto extraido",
    "size": len(DEFAULT_CONTENT),
    "created_at": "2026-10-09T12:30:00Z",
}


def make_settings(**overrides):
    defaults = {
        "http_retries": 3,
        "http_retry_backoff": 0.5,
        "http_timeout": 5.0,
        "max_upload_size": 10 * 1024 * 1024,
        "validator_service_url": "http://validator:8001",
        "extractor_service_url": "http://extractor:8002",
        "store_service_url": "http://store:8003",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


class FakeValidator:
    def __init__(self, result=None, error=None):
        self.result = {"valid": True} if result is None else result
        self.error = error
        self.calls = []

    def validate(self, file_bytes, filename):
        self.calls.append((file_bytes, filename))
        if self.error is not None:
            raise self.error
        return self.result


class FakeExtractor:
    def __init__(self, result=None, error=None):
        self.result = {"content": "texto extraido", "page_count": 1} if result is None else result
        self.error = error
        self.calls = []

    def extract(self, file_bytes, filename):
        self.calls.append((file_bytes, filename))
        if self.error is not None:
            raise self.error
        return self.result


class FakeStore:
    def __init__(self, result=None, error=None, document=None, documents=None):
        self.result = {"id": "abc123"} if result is None else result
        self.error = error
        self.document = document
        self.documents = documents if documents is not None else []
        self.calls = []

    def store(self, name, text, checksum, size=0):
        self.calls.append((name, text, checksum, size))
        if self.error is not None:
            raise self.error
        return self.result

    def get_by_id(self, doc_id):
        self.calls.append(("get_by_id", doc_id))
        if self.error is not None:
            raise self.error
        return self.document

    def get_by_checksum(self, checksum):
        self.calls.append(("get_by_checksum", checksum))
        if self.error is not None:
            raise self.error
        return self.document

    def list_all(self):
        self.calls.append(("list_all",))
        if self.error is not None:
            raise self.error
        return self.documents