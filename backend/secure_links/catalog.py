"""Catalog of the sensitive-information types a secure link can carry.

The catalog is the single source for the panel form, the public creation page
and the MCP tools: every payload is validated against it before encryption.
Adding a type means adding one entry here. Payment cards are deliberately
absent — card data must never be stored by ProjectApp.
"""

TEXT = 'text'
SECRET = 'secret'
TEXTAREA = 'textarea'
URL = 'url'

MAX_PAYLOAD_CHARS = 20_000


def _field(key, label_es, label_en, kind=TEXT, *, required=False, max_length=None):
    default_length = {TEXT: 200, SECRET: 2_000, TEXTAREA: 5_000, URL: 500}[kind]
    return {
        'key': key,
        'label_es': label_es,
        'label_en': label_en,
        'kind': kind,
        'required': required,
        'max_length': max_length or default_length,
    }


NOTE = _field('note', 'Nota', 'Note', TEXTAREA, max_length=2_000)

SECRET_TYPES = {
    'credentials': {
        'label_es': 'Credenciales de acceso',
        'label_en': 'Access credentials',
        'fields': [
            _field('service', 'Servicio o sitio', 'Service or site'),
            _field('url', 'URL de acceso', 'Login URL', URL),
            _field('username', 'Usuario o correo', 'Username or email'),
            _field('password', 'Contraseña', 'Password', SECRET, required=True),
            NOTE,
        ],
    },
    'api_key': {
        'label_es': 'API key o token',
        'label_en': 'API key or token',
        'fields': [
            _field('service', 'Servicio', 'Service'),
            _field('environment', 'Entorno', 'Environment'),
            _field('public_key', 'Clave pública', 'Public key', TEXTAREA, max_length=2_000),
            _field('secret_key', 'Clave secreta o token', 'Secret key or token', SECRET, required=True),
            NOTE,
        ],
    },
    'server_access': {
        'label_es': 'Acceso a servidor (SSH/SFTP)',
        'label_en': 'Server access (SSH/SFTP)',
        'fields': [
            _field('host', 'Host o IP', 'Host or IP', required=True),
            _field('port', 'Puerto', 'Port', max_length=10),
            _field('username', 'Usuario', 'Username', required=True),
            _field('credential', 'Contraseña o llave privada', 'Password or private key', SECRET, required=True, max_length=10_000),
            NOTE,
        ],
    },
    'database': {
        'label_es': 'Base de datos',
        'label_en': 'Database',
        'fields': [
            _field('engine', 'Motor', 'Engine'),
            _field('host', 'Host', 'Host', required=True),
            _field('port', 'Puerto', 'Port', max_length=10),
            _field('name', 'Nombre de la base', 'Database name'),
            _field('username', 'Usuario', 'Username', required=True),
            _field('password', 'Contraseña', 'Password', SECRET, required=True),
            NOTE,
        ],
    },
    'env_vars': {
        'label_es': 'Variables de entorno (.env)',
        'label_en': 'Environment variables (.env)',
        'fields': [
            _field('content', 'Contenido', 'Content', TEXTAREA, required=True, max_length=15_000),
            NOTE,
        ],
    },
    'bank_account': {
        'label_es': 'Datos bancarios',
        'label_en': 'Bank details',
        'fields': [
            _field('bank', 'Banco', 'Bank', required=True),
            _field('account_type', 'Tipo de cuenta', 'Account type'),
            _field('account_number', 'Número de cuenta', 'Account number', SECRET, required=True, max_length=60),
            _field('holder', 'Titular', 'Account holder', required=True),
            _field('holder_document', 'Documento del titular', 'Holder ID number', max_length=60),
            NOTE,
        ],
    },
    'recovery_codes': {
        'label_es': 'Códigos de recuperación (2FA)',
        'label_en': 'Recovery codes (2FA)',
        'fields': [
            _field('service', 'Servicio', 'Service', required=True),
            _field('codes', 'Códigos', 'Codes', SECRET, required=True, max_length=5_000),
            NOTE,
        ],
    },
    'confidential_message': {
        'label_es': 'Mensaje o comunicado confidencial',
        'label_en': 'Confidential message',
        'fields': [
            _field('subject', 'Asunto', 'Subject'),
            _field('message', 'Mensaje', 'Message', TEXTAREA, required=True, max_length=15_000),
        ],
    },
}


class CatalogError(ValueError):
    """Invalid type or payload; carries per-field errors for the API."""

    def __init__(self, errors):
        super().__init__('Contenido inválido.')
        self.errors = errors


def type_label(secret_type, language='es'):
    definition = SECRET_TYPES.get(secret_type)
    if definition is None:
        return secret_type
    return definition['label_en' if language == 'en' else 'label_es']


def catalog_payload():
    return [{'key': key, **definition} for key, definition in SECRET_TYPES.items()]


def clean_fields(secret_type, fields):
    """Validate ``fields`` for ``secret_type`` and return the stored payload.

    Unknown keys are rejected, every required field must be present, empty
    optional values are dropped and single-line values are stripped. Secret
    and multi-line values keep their exact characters.
    """
    definition = SECRET_TYPES.get(secret_type)
    if definition is None:
        raise CatalogError({'secret_type': ['Tipo de contenido no válido.']})
    if not isinstance(fields, dict):
        raise CatalogError({'fields': ['El contenido debe ser un objeto con los campos del tipo.']})
    allowed = {field['key']: field for field in definition['fields']}
    errors = {}
    unknown = sorted(set(fields) - set(allowed))
    if unknown:
        errors['fields'] = [f'Campos no permitidos: {", ".join(unknown)}.']
    cleaned = {}
    for key, field in allowed.items():
        value = fields.get(key, '')
        if value is None:
            value = ''
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            errors[key] = ['Debe ser texto.']
            continue
        value = str(value)
        if field['kind'] not in (SECRET, TEXTAREA):
            value = value.strip()
        if not value.strip():
            if field['required']:
                errors[key] = ['Este campo es obligatorio.']
            continue
        if len(value) > field['max_length']:
            errors[key] = [f'Máximo {field["max_length"]} caracteres.']
            continue
        cleaned[key] = value
    if not errors and sum(len(value) for value in cleaned.values()) > MAX_PAYLOAD_CHARS:
        errors['fields'] = [f'El contenido supera el máximo de {MAX_PAYLOAD_CHARS} caracteres.']
    if errors:
        raise CatalogError(errors)
    return cleaned


def labelled_fields(secret_type, payload, language='es'):
    """Project a decrypted payload as ordered, labelled values for display."""
    definition = SECRET_TYPES.get(secret_type, {'fields': []})
    label_key = 'label_en' if language == 'en' else 'label_es'
    return [
        {
            'key': field['key'],
            'label': field[label_key],
            'kind': field['kind'],
            'value': payload[field['key']],
        }
        for field in definition['fields']
        if payload.get(field['key'])
    ]
