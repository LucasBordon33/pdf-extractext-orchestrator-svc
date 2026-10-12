"""Contrato de entrada del endpoint de upload.

No define DTOs pydantic: el archivo llega como `UploadFile` (multipart,
campo `file`) y FastAPI exige declararlo como parámetro del endpoint, no
dentro de un modelo. La validación de que sea un PDF la hace el validador
(MICROSERVICIO 3), no el orquestador; el nombre del archivo viaja en
`UploadFile.filename`.
"""
