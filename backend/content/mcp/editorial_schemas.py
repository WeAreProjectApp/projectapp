"""Bounded format metadata, reusable by every editorial MCP module."""
TEXT_FORMATS_SCHEMA = {
    'type': 'object', 'maxProperties': 1000,
    'description': (
        'Formato explícito por campo (JSON Pointer). Ejemplo: '
        '{"/client_email_body":"markdown_html_v1"}. Markdown extendido conserva '
        'listas y tablas; HTML limitado conserva color, resaltado y alineación. '
        'WhatsApp usa whatsapp_v1 y su sintaxis propia. Omitir conserva el formato existente.'
    ),
    'propertyNames': {
        'type': 'string', 'pattern': '^/',
        'description': 'Ruta JSON Pointer del texto; el servicio comprueba que existe y admite formato.',
    },
    'patternProperties': {
        '^/': {
            'type': 'string', 'enum': ['plain', 'markdown', 'markdown_html_v1', 'whatsapp_v1'],
            'description': 'Formato que interpreta el contenido del texto señalado por la ruta.',
        },
    },
    'additionalProperties': False,
}
