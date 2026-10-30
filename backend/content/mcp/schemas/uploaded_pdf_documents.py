"""Explicit metadata inputs for uploaded PDF operations; files use owned assets."""
from copy import deepcopy

PDF_METADATA_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'title': {'type': 'string', 'maxLength': 255, 'description': 'Título no vacío.'},
        'client': {'type': ['integer', 'null'], 'minimum': 1, 'description': 'ID de UserProfile cliente; null desvincula.'},
        'project': {'type': ['integer', 'null'], 'minimum': 1, 'description': 'Proyecto del cliente; null desvincula.'},
        'folder_id': {'type': ['integer', 'null'], 'minimum': 1, 'description': 'Carpeta activa y manual; null sitúa en raíz.'},
        'adopt_folder_client': {'type': 'boolean', 'description': 'Adopta explícitamente el cliente de la carpeta destino.'},
        'client_name': {'type': 'string', 'description': 'Nombre del cliente mostrado en el gestor.'},
        'language': {'type': 'string', 'enum': ['es', 'en'], 'description': 'Idioma de identificación del documento.'},
        'status': {'type': 'string', 'enum': ['draft', 'published', 'archived'], 'description': 'Estado editorial heredado; no cambia publicación ni archivo.'},
        'is_client_visible': {'type': 'boolean', 'description': 'Publicación explícita en el portal del cliente.'},
        'tag_ids': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'description': 'IDs de etiquetas existentes.'},
        'client_email_subject': {'type': 'string', 'maxLength': 255, 'description': 'Asunto privado preparado para el cliente.'},
        'client_email_body': {'type': 'string', 'description': 'Correo privado preparado para el cliente.'},
        'client_whatsapp_message': {'type': 'string', 'description': 'WhatsApp privado preparado para el cliente.'},
        'client_custom_notes': {'type': 'array', 'description': 'Notas privadas ordenadas.', 'items': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['title', 'content'], 'additionalProperties': False}},
    },
}
PDF_CREATE_SCHEMA = deepcopy(PDF_METADATA_SCHEMA)
PDF_CREATE_SCHEMA['required'] = ['title']

# Moves use update_document/move_documents with the shared ownership planner.
PDF_METADATA_SCHEMA['properties'].pop('folder_id')
PDF_METADATA_SCHEMA['properties'].pop('adopt_folder_client')
