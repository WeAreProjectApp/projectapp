"""
Tool registry for the Clients MCP connector.

Lets claude.ai manage proposal clients (the ``/panel/clients`` page): search,
list, inspect, create, update and delete client profiles. Clients are
``accounts.UserProfile`` rows with role=client; they are the canonical identity
shared by proposals, diagnostics, documents, accounting and communications.

Guardrails baked in (mirror the panel exactly, by delegating to the same
service):
- Writes always go through ``proposal_client_service`` (never a bare
  ``serializer.save()``) so proposal snapshots stay in sync and email-in-use
  conflicts are enforced.
- Delete only succeeds for true orphans across every protected module;
  otherwise the exact ``client_has_*:N`` reason is surfaced.

Each entry: {'name', 'description', 'input_schema', 'handler'}. Handlers take
the raw ``arguments`` dict, return a JSON-serializable dict, and raise
ToolError for business errors.
"""
from accounts.models import UserProfile
from accounts.serializers import ProjectListSerializer
from accounts.services import proposal_client_service
from content.mcp.protocol import ToolError
from content.serializers.diagnostic import DiagnosticListSerializer
from content.serializers.proposal import ProposalListSerializer
from content.serializers.proposal_clients import (
    ProposalClientSearchSerializer,
    ProposalClientSerializer,
)
# Reuse the panel view's annotated queryset + helpers so the MCP exposes the
# exact same computed fields (counts, last_status, is_orphan) as /panel/clients.
from content.views.proposal_clients import (
    _ORPHAN_PREDICATE,
    _base_queryset,
    _get_profile_or_404,
)


def _get_client_or_error(client_id):
    profile = _get_profile_or_error_none(client_id)
    if profile is None:
        raise ToolError(
            f'No existe un cliente con id={client_id}. '
            'Usa search_clients o list_clients para ver los disponibles.'
        )
    return profile


def _get_profile_or_error_none(client_id):
    try:
        return _get_profile_or_404(int(client_id))
    except (TypeError, ValueError):
        return None


# ── Handlers ─────────────────────────────────────────────────────────────────

def search_clients(arguments):
    query = (arguments.get('q') or '').strip()
    qs = UserProfile.objects.clients()
    if query:
        from django.db.models import Q
        qs = qs.filter(
            Q(user__email__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(company_name__icontains=query)
        )
    qs = qs.order_by('-updated_at')[:20]
    return {'results': ProposalClientSearchSerializer(qs, many=True).data}


def list_clients(arguments):
    from django.db.models import Q
    qs = _base_queryset()

    search = (arguments.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(company_name__icontains=search)
        )

    orphans = arguments.get('orphans')
    if orphans is True:
        qs = qs.filter(**_ORPHAN_PREDICATE)
    elif orphans is False:
        qs = qs.exclude(**_ORPHAN_PREDICATE)

    # Same default as the panel list: archived clients are out unless asked
    # for. The connector was returning them mixed in with the active ones,
    # with nothing on the row saying so, which is how an assistant ends up
    # proposing work to a client that was deliberately put away.
    if arguments.get('archived') is True:
        qs = qs.filter(archived_at__isnull=False)
    else:
        qs = qs.filter(archived_at__isnull=True)

    try:
        limit = min(int(arguments.get('limit', 100) or 100), 500)
    except (TypeError, ValueError):
        raise ToolError('limit debe ser un entero.')

    qs = qs.prefetch_related('proposals').order_by('-last_proposal_at', '-updated_at')[:limit]
    results = ProposalClientSerializer(qs, many=True).data
    return {'count': len(results), 'results': results}


def get_client(arguments):
    profile = _get_client_or_error(arguments.get('client_id'))
    payload = ProposalClientSerializer(profile).data
    proposals = profile.proposals.select_related('client__user').order_by('-created_at')
    payload['proposals'] = ProposalListSerializer(proposals, many=True).data
    projects = profile.user.projects.select_related('client__profile').order_by('-created_at')
    payload['projects'] = ProjectListSerializer(projects, many=True).data
    diagnostics = profile.web_app_diagnostics.select_related('client__user').order_by('-created_at')
    payload['diagnostics'] = DiagnosticListSerializer(diagnostics, many=True).data
    return payload


def create_client(arguments):
    name = (arguments.get('name') or '').strip()
    email = (arguments.get('email') or '').strip()
    phone = (arguments.get('phone') or '').strip()
    company = (arguments.get('company') or '').strip()

    if not name and not email and not company:
        raise ToolError('Debes proporcionar al menos un nombre, email o empresa.')

    try:
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name=name, email=email, phone=phone, company=company,
        )
    except ValueError as exc:
        raise ToolError(f'Datos de cliente inválidos: {exc}')

    return ProposalClientSerializer(_get_profile_or_404(profile.pk)).data


def update_client(arguments):
    profile = _get_client_or_error(arguments.get('client_id'))

    payload = {}
    for key in ('name', 'email', 'phone', 'company'):
        if key in arguments:
            payload[key] = arguments[key]

    if not payload:
        raise ToolError(
            'No se indicó ningún campo para actualizar. Envía al menos uno de: '
            'name, email, phone, company.'
        )

    try:
        proposal_client_service.update_client_profile(profile, **payload)
    except ValueError as exc:
        raise ToolError(f'No se pudo actualizar el cliente: {exc}')

    return ProposalClientSerializer(_get_profile_or_404(profile.pk)).data


def delete_client(arguments):
    profile = _get_client_or_error(arguments.get('client_id'))
    profile_id = profile.pk
    try:
        proposal_client_service.delete_orphan_client(profile)
    except ValueError as exc:
        # Service raises 'client_has_proposals:N' / 'client_has_projects:N' /
        # 'client_has_diagnostics:N' / 'client_has_incomes:N' /
        # 'client_has_hostings:N' / 'client_has_communications:N'. Preserve
        # the exact reason for the calling model.
        raise ToolError(
            f'No se puede eliminar: el cliente aún tiene referencias ({exc}). '
            'Elimina o reasigna esas propuestas/proyectos/diagnósticos/'
            'ingresos/hostings/comunicaciones primero.'
        )
    return {'deleted': True, 'id': profile_id}


# ── Registry ─────────────────────────────────────────────────────────────────

_CLIENT_ID_PROP = {
    'client_id': {'type': 'integer', 'description': 'ID del perfil de cliente.'},
}

CLIENT_TOOLS = [
    {
        'name': 'search_clients',
        'description': (
            'Autocompletado rápido de clientes. Busca por email, nombre o '
            'empresa (parcial) y devuelve hasta 20 resultados resumidos. '
            'Úsalo para encontrar el client_id que necesitan otras tools '
            '(p. ej. crear una propuesta o un diagnóstico). Incluye los datos '
            'canónicos de facturación: nombre legal, identificación y dirección.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string', 'description': 'Texto a buscar (parcial).'},
            },
        },
        'handler': search_clients,
    },
    {
        'name': 'list_clients',
        'description': (
            'Lista clientes con métricas de propuestas, proyectos, diagnósticos, '
            'documentos, contabilidad, correos y comunicaciones. Devuelve sólo '
            'clientes activos salvo que pidas archived=true. Filtros: search '
            '(texto), orphans (true=sólo sin propuestas, proyectos, diagnósticos, '
            'ingresos, hostings ni hilos; false=el resto), archived '
            '(true=sólo archivados) y limit.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'search': {'type': 'string'},
                'orphans': {'type': 'boolean'},
                'archived': {'type': 'boolean'},
                'limit': {'type': 'integer', 'default': 100, 'maximum': 500},
            },
        },
        'handler': list_clients,
    },
    {
        'name': 'get_client',
        'description': (
            'Devuelve un cliente con propuestas, proyectos y diagnósticos '
            'anidados, más las métricas actuales de documentos, contabilidad, '
            'correos y comunicaciones y los datos canónicos de facturación '
            '(nombre legal, identificación, correo y dirección). Consulta cada módulo en su propio MCP '
            'para abrir esas colecciones completas.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _CLIENT_ID_PROP,
            'required': ['client_id'],
        },
        'handler': get_client,
    },
    {
        'name': 'create_client',
        'description': (
            'Crea un cliente nuevo (sin propuesta ni email de invitación). '
            'Requiere al menos uno de name/email/company. Si omites el email se '
            'genera un placeholder. No reutiliza cuentas de administrador.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'email': {'type': 'string'},
                'phone': {'type': 'string'},
                'company': {'type': 'string'},
            },
        },
        'handler': create_client,
    },
    {
        'name': 'update_client',
        'description': (
            'Actualiza un cliente (parcial) y propaga el cambio a todas sus '
            'propuestas. Envía client_id y al menos uno de: name, email, '
            'phone, company. Falla si el email ya está en uso por otro cliente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_CLIENT_ID_PROP,
                'name': {'type': 'string'},
                'email': {'type': 'string'},
                'phone': {'type': 'string'},
                'company': {'type': 'string'},
            },
            'required': ['client_id'],
        },
        'handler': update_client,
    },
    {
        'name': 'delete_client',
        'description': (
            'Elimina un cliente SÓLO si es huérfano: sin propuestas, proyectos, '
            'diagnósticos, ingresos, hostings ni hilos de comunicaciones. Si '
            'tiene referencias, la operación falla indicando el módulo y total.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _CLIENT_ID_PROP,
            'required': ['client_id'],
        },
        'handler': delete_client,
    },
]
