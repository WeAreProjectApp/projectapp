"""Discoverable proposal inputs derived from the Panel's validation contract."""
from copy import deepcopy

from rest_framework.schemas.openapi import AutoSchema

from content.mcp.protocol import ToolError
from content.serializers.proposal import (
    ContractParamsSerializer,
    EmailTemplateConfigSerializer,
    ProposalAlertSerializer,
    ProposalCreateUpdateSerializer,
    ProposalDefaultConfigSerializer,
    ProposalFromJSONSerializer,
    ProposalSectionUpdateSerializer,
)
from content.serializers.service_contract_settings import (
    CompanyServiceSettingsSerializer,
)


def object_schema(properties, required=()):
    schema = {'type': 'object', 'properties': properties, 'additionalProperties': False}
    if required:
        schema['required'] = list(required)
    return schema


def _json_schema(value):
    """Translate DRF's OpenAPI nullable flag into MCP JSON Schema types."""
    if isinstance(value, list):
        return [_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _json_schema(item) for key, item in value.items() if key != 'nullable'}
    if value.get('nullable'):
        result = {'anyOf': [result, {'type': 'null'}]}
    return result


def writable_schema(serializer_class, *, partial=False, exclude=()):
    """Expose writable fields without instantiating objects or querying the DB."""
    serializer = serializer_class(partial=partial)
    schema = AutoSchema().map_serializer(serializer)
    properties = {
        key: _json_schema(value) for key, value in schema['properties'].items()
        if not serializer.fields[key].read_only and key not in exclude
    }
    required = () if partial else [key for key in schema.get('required', []) if key in properties]
    return object_schema(properties, required)


def check_known_fields(payload, schema):
    """Reject misspelled fields instead of a successful, silent no-op."""
    if not isinstance(payload, dict):
        raise ToolError('El contenido debe ser un objeto JSON.')
    properties = schema.get('properties')
    if properties is None:
        return
    unknown = set(payload) - set(properties)
    if unknown and schema.get('additionalProperties') is False:
        raise ToolError('Campos no editables: ' + ', '.join(sorted(unknown)))
    for key, value in payload.items():
        field = properties.get(key, {})
        if field.get('type') == 'object' and 'properties' in field:
            check_known_fields(value, field)


VARIANT = {'type': 'string', 'enum': ['combined', 'product', 'service']}
CONTRACT_PARAMS = writable_schema(ContractParamsSerializer, partial=True)
for _name in ('service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days'):
    CONTRACT_PARAMS['properties'][_name] = {
        'oneOf': [{'type': 'integer', 'minimum': 1, 'maximum': 999}, {'type': 'string'}],
        'description': 'Entero entre 1 y 999 o texto contractual histórico.',
    }
CONTRACT_UPDATE = object_schema({'variant': VARIANT, 'contract_params': CONTRACT_PARAMS}, ('contract_params',))
SETTINGS_UPDATE = writable_schema(ProposalCreateUpdateSerializer, partial=True, exclude=('status',))
DEFAULTS_UPDATE = writable_schema(ProposalDefaultConfigSerializer, partial=True)
DEFAULTS_UPDATE['properties']['base_updated_at'] = {
    'type': ['string', 'null'], 'description': 'updated_at obtenido en get_proposal_defaults; rechaza cambios concurrentes.',
}

PAYLOAD_SCHEMAS = {
    'update_proposal_settings': SETTINGS_UPDATE,
    'update_proposal_contract': CONTRACT_UPDATE,
    'save_proposal_contract_negotiation': object_schema({'contract_params': CONTRACT_PARAMS}, ('contract_params',)),
    'update_proposal_contract_modality': object_schema({
        'contract_modality': {'type': 'string', 'enum': ['single', 'split']},
        'change_note': {'type': 'string', 'maxLength': 4000},
        'contract_params': object_schema({key: CONTRACT_PARAMS['properties'][key] for key in (
            'service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days')}),
        'conflict_resolution': {'type': 'string', 'enum': ['use_origin']},
    }, ('contract_modality',)),
    'update_proposal_service_settings': writable_schema(CompanyServiceSettingsSerializer),
    'update_proposal_section': writable_schema(ProposalSectionUpdateSerializer, partial=True),
    'update_proposal_defaults': DEFAULTS_UPDATE,
    'update_email_template': writable_schema(EmailTemplateConfigSerializer, partial=True),
    'send_multi_proposal': object_schema({
        'proposal_ids': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'minItems': 2, 'maxItems': 10},
    }, ('proposal_ids',)),
    'render_proposal_email_markdown_pdf': object_schema({
        'title': {'type': 'string'}, 'markdown': {'type': 'string'},
        'include_portada': {'type': 'boolean'},
        'include_subportada': {'type': 'boolean'},
        'include_contraportada': {'type': 'boolean'},
    }, ('title', 'markdown')),
}


TEXT = {'type': 'string'}
FLAG = {'type': 'boolean'}
NUMBER = {'type': 'integer', 'minimum': 1}
IDS = {'type': 'array', 'items': NUMBER}
JSON_OBJECT = {'type': 'object', 'additionalProperties': True}
LANGUAGE = {'type': 'string', 'enum': ['es', 'en']}
EMAIL = {'type': 'string', 'format': 'email'}
COMPOSED_EMAIL = object_schema({
    'recipient_email': {**EMAIL, 'description': 'Alias histórico para un destinatario; se conserva por compatibilidad.'},
    'recipient_emails': {'type': 'array', 'items': EMAIL, 'maxItems': 10},
    'cc_emails': {'type': 'array', 'items': EMAIL, 'maxItems': 10},
    'subject': TEXT, 'greeting': TEXT, 'footer': TEXT,
    'sections': {'oneOf': [
        {'type': 'array', 'items': {'oneOf': [TEXT, object_schema({'text': TEXT, 'markdown': FLAG})]}},
        TEXT,
    ]},
    'doc_refs': {'oneOf': [{'type': 'array', 'items': JSON_OBJECT}, TEXT]},
}, ('subject',))
COMPOSED_EMAIL['anyOf'] = [
    {'required': ['recipient_emails']}, {'required': ['recipient_email']},
]
PAYLOAD_SCHEMAS.update({
    'update_proposal_from_json': writable_schema(ProposalFromJSONSerializer),
    'create_proposal_section': object_schema({'section_type': TEXT, 'title': TEXT}, ('section_type',)),
    'reorder_proposal_sections': object_schema({'sections': {
        'type': 'array', 'items': object_schema({'id': NUMBER, 'order': {'type': 'integer'}}, ('id', 'order')),
    }}, ('sections',)),
    'preview_proposal_section_sync': object_schema({'content_json': JSON_OBJECT}, ('content_json',)),
    'apply_proposal_section_sync': object_schema({'content_json': JSON_OBJECT}, ('content_json',)),
    'create_proposal_alert': writable_schema(ProposalAlertSerializer),
    'dismiss_proposal_alert': object_schema({'computed_alert_type': TEXT, 'ref_date': TEXT}),
    'log_proposal_activity': object_schema({'change_type': TEXT, 'description': TEXT}, ('change_type', 'description')),
    'bulk_action_proposals': object_schema({'ids': IDS, 'action': {'type': 'string', 'enum': ['delete', 'expire', 'resend']}}, ('ids', 'action')),
    'reset_proposal_defaults': object_schema({'language': LANGUAGE}),
    'upload_proposal_document': object_schema({
        'title': TEXT, 'document_type': {'type': 'string', 'enum': ['amendment', 'legal_annex', 'client_document', 'other']},
        'custom_type_label': TEXT,
    }),
    'send_proposal_documents': object_schema({
        'documents': {'type': 'array', 'items': {'type': 'string', 'enum': ['draft_contract', 'commercial', 'technical']}},
        'additional_doc_ids': IDS, 'subject': TEXT, 'greeting': TEXT, 'body': TEXT, 'footer': TEXT,
        'document_descriptions': {'type': 'array', 'items': object_schema({'name': TEXT, 'description': TEXT})},
    }),
    'send_branded_email': COMPOSED_EMAIL,
    'send_custom_proposal_email': COMPOSED_EMAIL,
    'update_proposal_stage': object_schema({
        'start_date': {'type': ['string', 'null'], 'format': 'date'},
        'end_date': {'type': ['string', 'null'], 'format': 'date'},
    }),
})


def guarded_arguments(arguments, tool):
    """Accept the documented flat arguments or the existing data envelope."""
    if not isinstance(arguments, dict):
        raise ToolError('Los argumentos deben ser un objeto JSON.')
    args = deepcopy(arguments)
    operation = tool['_panel_operation']
    data = args.get('data', {})
    check_known_fields(data, operation['payload_schema'])
    payload = {
        key: value for key, value in args.items()
        if key not in (*operation['path_params'], *operation['asset_fields'], 'data', 'if_match', 'query')
    }
    check_known_fields(payload, operation['payload_schema'])
    overlap = set(payload) & set(data)
    if overlap:
        raise ToolError('No repitas campos en data y en los argumentos: ' + ', '.join(sorted(overlap)))
    return args
