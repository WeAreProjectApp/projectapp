"""
Tool registry for the Proposals MCP connector.

Lets claude.ai manage business proposals (/panel/proposals): browse, inspect,
create and edit from a JSON payload, drive the status lifecycle, send/resend,
duplicate, delete, and create share links.

Create/update reuse the panel's from-JSON pipeline via
`proposal_service.build_proposal_from_json` / `apply_proposal_json_update` — the
same code the panel views call — so the load-bearing guardrails (protect
default FR groups/modules, stamp item ids, normalize technical-doc links) never
drift. Status/send flows delegate to `ProposalService`.

Guardrails (mirror the panel):
- Status changes respect `BusinessProposal.ALLOWED_TRANSITIONS`; draft→sent is
  routed through `send_proposal` (dispatches email + schedules reminders).
- Sending requires a valid client email and a personalized email message (the
  service raises otherwise).
- Delete is blocked when the proposal is launched to the platform (ProtectedError).

Each entry: {'name', 'description', 'input_schema', 'handler'}.
"""
import copy

from django.db.models import ProtectedError

from content.mcp.protocol import ToolError
from content.models import (
    BusinessProposal,
    ProposalChangeLog,
    ProposalShareLink,
)
from content.serializers.proposal import (
    SECTION_TYPE_TO_KEY,
    ProposalDetailSerializer,
    ProposalFromJSONSerializer,
    ProposalListSerializer,
    ProposalShareLinkSerializer,
)
from content.services import proposal_service, proposal_status_service
from content.services.proposal_service import ProposalService


def _serializer_errors_to_message(errors):
    import json
    return 'JSON inválido para la propuesta: ' + json.dumps(errors, ensure_ascii=False, default=str)


def _get_proposal_or_error(proposal_id):
    try:
        return BusinessProposal.objects.get(pk=int(proposal_id))
    except (BusinessProposal.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe una propuesta con id={proposal_id}.')


def _detail(proposal):
    return ProposalDetailSerializer(proposal, context={'is_admin': True}).data


# ── Handlers ─────────────────────────────────────────────────────────────────

def get_proposal_template(arguments):
    lang = arguments.get('lang', 'es')
    if lang not in ('es', 'en'):
        lang = 'es'
    default_sections = ProposalService.get_default_sections(lang)
    template = {}
    for section_cfg in default_sections:
        json_key = SECTION_TYPE_TO_KEY.get(section_cfg['section_type'], section_cfg['section_type'])
        template[json_key] = copy.deepcopy(section_cfg['content_json'])
    return {
        'template': template,
        'meta': {
            'required_fields': ['general.clientName'],
            'optional_metadata': [
                'title', 'client_email', 'client_phone', 'language',
                'email_intro',
                'total_investment', 'currency', 'nationality',
                'project_type', 'project_type_custom', 'market_type',
                'market_type_custom', 'show_contract_terms', 'show_explainer_video',
            ],
        },
        'notes': (
            'Envía este shape (claves camelCase por sección) en `sections` a '
            'create_proposal/update_proposal. Los grupos y módulos de '
            'functionalRequirements se fusionan con los defaults (no se pueden '
            'eliminar). `email_intro` debe explicar problema, solución y resultado '
            'de negocio; es obligatorio antes de enviar. Para la guía completa de redacción usa la plantilla '
            'descargable del panel (/panel/proposals).'
        ),
    }


def list_proposals(arguments):
    qs = BusinessProposal.objects.select_related('client__user').all()
    if arguments.get('status'):
        qs = qs.filter(status=arguments['status'])
    if arguments.get('client_id'):
        qs = qs.filter(client_id=arguments['client_id'])
    return {'results': ProposalListSerializer(list(qs), many=True).data}


def get_proposal(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    return _detail(proposal)


def create_proposal(arguments):
    serializer = ProposalFromJSONSerializer(data=arguments)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    proposal, unmapped_keys = proposal_service.build_proposal_from_json(serializer.validated_data)
    payload = _detail(proposal)
    if unmapped_keys:
        payload['warnings'] = [f'Claves de sección ignoradas: {", ".join(unmapped_keys)}.']
    return payload


def update_proposal(arguments):
    proposal_id = arguments.get('proposal_id')
    proposal = _get_proposal_or_error(proposal_id)
    data = {k: v for k, v in arguments.items() if k != 'proposal_id'}
    serializer = ProposalFromJSONSerializer(data=data, context={'proposal': proposal})
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    try:
        proposal, _updated, unmapped_keys = proposal_service.apply_proposal_json_update(
            proposal, serializer.validated_data,
        )
    except ValueError as exc:  # includes ProposalActionError
        raise ToolError(str(exc))
    payload = _detail(proposal)
    if unmapped_keys:
        payload['warnings'] = [f'Claves de sección ignoradas: {", ".join(unmapped_keys)}.']
    return payload


def update_proposal_status(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    try:
        proposal_status_service.change_status(
            proposal, arguments.get('status'),
            source='vía MCP', acting_user_id=None,
        )
    except ValueError as exc:  # includes ProposalActionError
        raise ToolError(str(exc))
    return _detail(proposal)


def send_proposal(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    try:
        ProposalService.send_proposal(proposal)
    except ValueError as exc:
        raise ToolError(str(exc))
    ProposalChangeLog.objects.create(
        proposal=proposal, change_type='sent', actor_type='seller',
        description=f'Proposal sent to {proposal.client_email} (vía MCP).',
    )
    return _detail(proposal)


def resend_proposal(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    try:
        ProposalService.resend_proposal(
            proposal, email_intro=arguments.get('email_intro'),
        )
    except ValueError as exc:
        raise ToolError(str(exc))
    return _detail(proposal)


def delete_proposal(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    proposal_id = proposal.id
    try:
        proposal.delete()
    except ProtectedError:
        raise ToolError(
            'No se puede eliminar: la propuesta está vinculada a un proyecto '
            'lanzado a la plataforma. Desvincula el proyecto primero.'
        )
    return {'deleted': True, 'id': proposal_id}


def duplicate_proposal(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    new_proposal = proposal_service.duplicate_proposal(proposal, via_mcp=True)
    return _detail(new_proposal)


def create_share_link(arguments):
    proposal = _get_proposal_or_error(arguments.get('proposal_id'))
    if not proposal.is_active:
        raise ToolError('La propuesta no está activa; no se pueden crear enlaces para compartir.')
    name = (arguments.get('name') or '').strip()
    if not name:
        raise ToolError('name es obligatorio.')
    email = (arguments.get('email') or '').strip()
    share_link = ProposalShareLink.objects.create(
        proposal=proposal, shared_by_name=name, shared_by_email=email,
    )
    try:
        from content.services.proposal_email_service import ProposalEmailService
        ProposalEmailService.send_share_notification(proposal, share_link)
    except Exception:
        pass
    return ProposalShareLinkSerializer(share_link).data


# ── Registry ─────────────────────────────────────────────────────────────────

_PROPOSAL_ID_PROP = {'proposal_id': {'type': 'integer', 'description': 'ID de la propuesta.'}}
_STATUS_ENUM = [c[0] for c in BusinessProposal.Status.choices]

_FROM_JSON_PROPS = {
    'title': {'type': 'string'},
    'client_name': {'type': 'string'},
    'client_id': {'type': 'integer', 'description': 'ID de cliente existente (opcional).'},
    'client_email': {'type': 'string'},
    'email_intro': {
        'type': 'string',
        'description': (
            'Mensaje personalizado en texto plano que explica el problema, la '
            'solución propuesta y el resultado de negocio esperado.'
        ),
    },
    'client_phone': {'type': 'string'},
    'client_company': {'type': 'string'},
    'project_type': {'type': 'string'},
    'project_type_custom': {'type': 'string'},
    'market_type': {'type': 'string'},
    'market_type_custom': {'type': 'string'},
    'language': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'},
    'total_investment': {'type': ['number', 'string'], 'default': 0},
    'currency': {'type': 'string', 'enum': ['COP', 'USD'], 'default': 'COP'},
    'nationality': {
        'type': 'string', 'enum': ['COL', 'EXT', 'USA'], 'default': 'COL',
    },
    'expires_at': {'type': 'string', 'description': 'ISO 8601 con timezone (opcional).'},
    'reminder_days': {'type': 'integer', 'default': 10},
    'urgency_reminder_days': {'type': 'integer', 'default': 15},
    'discount_percent': {'type': ['number', 'string'], 'default': 0},
    'show_explainer_video': {
        'type': 'boolean',
        'default': True,
        'description': 'Permite el video de bienvenida si el control global y las cuatro opciones públicas están disponibles.',
    },
    'show_contract_terms': {
        'type': 'boolean',
        'default': True,
        'description': 'Muestra u oculta los términos contractuales genéricos.',
    },
    'sections': {
        'type': 'object',
        'description': 'Dict de secciones camelCase → content_json. Requiere general.clientName. Usa get_proposal_template.',
    },
}

PROPOSAL_TOOLS = [
    {
        'name': 'get_proposal_template',
        'description': (
            'Devuelve el esqueleto JSON de secciones (claves camelCase → '
            'content_json) para crear/editar una propuesta, con los campos '
            'requeridos. Param: lang (es/en).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'lang': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'}},
        },
        'handler': get_proposal_template,
    },
    {
        'name': 'list_proposals',
        'description': 'Lista propuestas. Filtros: status, client_id.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'enum': _STATUS_ENUM},
                'client_id': {'type': 'integer'},
            },
        },
        'handler': list_proposals,
    },
    {
        'name': 'get_proposal',
        'description': 'Devuelve el detalle admin completo de una propuesta (todas las secciones).',
        'input_schema': {'type': 'object', 'properties': _PROPOSAL_ID_PROP, 'required': ['proposal_id']},
        'handler': get_proposal,
    },
    {
        'name': 'create_proposal',
        'description': (
            'Crea una propuesta desde JSON. Requiere title, client_name y '
            'sections (con general.clientName). Las secciones faltantes usan '
            'defaults; los grupos/módulos base de functionalRequirements no se '
            'pueden eliminar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _FROM_JSON_PROPS,
            'required': ['title', 'client_name', 'sections'],
        },
        'handler': create_proposal,
    },
    {
        'name': 'update_proposal',
        'description': (
            'Reimporta una propuesta desde JSON. Requiere proposal_id, title, '
            'client_name y sections (con general.clientName); sólo se reemplazan '
            'las secciones presentes, pero los metadatos se validan como payload completo.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_PROPOSAL_ID_PROP, **_FROM_JSON_PROPS},
            'required': ['proposal_id', 'title', 'client_name', 'sections'],
        },
        'handler': update_proposal,
    },
    {
        'name': 'update_proposal_status',
        'description': (
            'Cambia el estado a cualquier valor (modo admin). Los efectos '
            'de correo en draft→sent y accepted→finished se disparan en sus '
            'transiciones naturales; los saltos forzados solo guardan y loggean. '
            'accepted no crea proyectos. Usa review_proposal_approval para '
            'completar los casos pendientes de cliente, proyecto y documentos.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_PROPOSAL_ID_PROP, 'status': {'type': 'string', 'enum': _STATUS_ENUM}},
            'required': ['proposal_id', 'status'],
        },
        'handler': update_proposal_status,
    },
    {
        'name': 'send_proposal',
        'description': (
            'Envía la propuesta al cliente y agenda recordatorios. Requiere '
            'client_email válido y email_intro no vacío.'
        ),
        'input_schema': {'type': 'object', 'properties': _PROPOSAL_ID_PROP, 'required': ['proposal_id']},
        'handler': send_proposal,
    },
    {
        'name': 'resend_proposal',
        'description': (
            'Reenvía al cliente una propuesta que ya salió de borrador, usando '
            'el mismo servicio de correo y validaciones del panel. Puede recibir '
            'email_intro para editar y guardar el mensaje antes del reenvío; si '
            'se omite, conserva el mensaje guardado.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_PROPOSAL_ID_PROP, 'email_intro': _FROM_JSON_PROPS['email_intro']},
            'required': ['proposal_id'],
        },
        'handler': resend_proposal,
    },
    {
        'name': 'delete_proposal',
        'description': 'Elimina una propuesta. Falla si está vinculada a un proyecto de plataforma.',
        'input_schema': {'type': 'object', 'properties': _PROPOSAL_ID_PROP, 'required': ['proposal_id']},
        'handler': delete_proposal,
    },
    {
        'name': 'duplicate_proposal',
        'description': 'Duplica una propuesta (copia todas sus secciones) reseteada a borrador.',
        'input_schema': {'type': 'object', 'properties': _PROPOSAL_ID_PROP, 'required': ['proposal_id']},
        'handler': duplicate_proposal,
    },
    {
        'name': 'create_share_link',
        'description': 'Crea un enlace de compartición rastreable para una propuesta activa. Requiere name.',
        'input_schema': {
            'type': 'object',
            'properties': {
                **_PROPOSAL_ID_PROP,
                'name': {'type': 'string'},
                'email': {'type': 'string'},
            },
            'required': ['proposal_id', 'name'],
        },
        'handler': create_share_link,
    },
]
