"""
Tool registry for the Diagnostics MCP connector.

Lets claude.ai manage web-app diagnostics (/panel/diagnostics): list, inspect,
create (seeded from a client), edit general data and sections, drive the status
lifecycle, send the initial/final documents, and read the static markdown
templates.

Creation is service-driven (`diagnostic_service.create_diagnostic`) and needs
an existing client_id — pair this with the Clients connector. There is no
create-from-JSON: content lives in the 8 seeded sections, edited afterwards.

Guardrails (mirror the panel by delegating to `diagnostic_service`):
- Status changes go through `transition_status` (whitelisted transitions).
- Sends transition + email in one step.
- Delete is unrestricted here (matches the backend; the client FK is PROTECTed
  and the client-orphan check still applies elsewhere).

Each entry: {'name', 'description', 'input_schema', 'handler'}.
"""
from accounts.models import UserProfile
from accounts.services.proposal_client_service import update_client_profile
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import closed_object, close_root_schemas, open_object
from content.models import (
    DiagnosticChangeLog,
    DiagnosticSection,
    WebAppDiagnostic,
)
from content.serializers.diagnostic import (
    DiagnosticDetailSerializer,
    DiagnosticListSerializer,
    DiagnosticSectionSerializer,
    DiagnosticSectionUpdateSerializer,
    DiagnosticUpdateSerializer,
)
from content.services import diagnostic_service
from content.views.diagnostic import _admin_qs
from content.views.diagnostic_template import TEMPLATES, TEMPLATES_DIR, _stat


def _serializer_errors_to_message(errors):
    import json
    return 'Datos inválidos: ' + json.dumps(errors, ensure_ascii=False, default=str)


def _get_diagnostic_or_error(diagnostic_id):
    try:
        return WebAppDiagnostic.objects.get(pk=int(diagnostic_id))
    except (WebAppDiagnostic.DoesNotExist, TypeError, ValueError):
        raise ToolError(f'No existe un diagnóstico con id={diagnostic_id}.')


def _detail(diagnostic):
    fresh = _admin_qs(include_attachments=True).get(pk=diagnostic.pk)
    return DiagnosticDetailSerializer(fresh).data


# ── Handlers ─────────────────────────────────────────────────────────────────

def list_diagnostics(arguments):
    qs = _admin_qs()
    if arguments.get('status'):
        qs = qs.filter(status=arguments['status'])
    if arguments.get('client'):
        qs = qs.filter(client_id=arguments['client'])
    return {'results': DiagnosticListSerializer(qs, many=True).data}


def get_diagnostic(arguments):
    diagnostic = _get_diagnostic_or_error(arguments.get('diagnostic_id'))
    return _detail(diagnostic)


def create_diagnostic(arguments):
    client_id = arguments.get('client_id')
    if not client_id:
        raise ToolError('client_id es obligatorio. Usa el connector de clientes para encontrarlo.')
    client = UserProfile.objects.filter(pk=client_id, role=UserProfile.ROLE_CLIENT).first()
    if client is None:
        raise ToolError(f'No existe un cliente con id={client_id}.')

    language = (arguments.get('language') or 'es').lower()
    if language not in ('es', 'en'):
        language = 'es'
    title = (arguments.get('title') or '').strip()

    diagnostic = diagnostic_service.create_diagnostic(
        client=client, language=language, title=title, created_by=None,
    )
    return _detail(diagnostic)


def update_diagnostic(arguments):
    diagnostic = _get_diagnostic_or_error(arguments.get('diagnostic_id'))
    data = {k: v for k, v in arguments.items() if k != 'diagnostic_id'}
    if not data:
        raise ToolError('No se indicó ningún campo para actualizar.')
    serializer = DiagnosticUpdateSerializer(diagnostic, data=data, partial=True)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    propagate = serializer.validated_data.get('propagate_client_updates', False)
    serializer.save()
    if propagate:
        update_client_profile(
            diagnostic.client,
            name=diagnostic.client_name or None,
            email=diagnostic.client_email or None,
            phone=diagnostic.client_phone or None,
            company=diagnostic.client_company or None,
        )
    diagnostic_service.log_change(
        diagnostic,
        change_type=DiagnosticChangeLog.ChangeType.UPDATED,
        description='Datos generales actualizados (vía MCP).',
        actor_type=DiagnosticChangeLog.ActorType.SELLER,
    )
    return _detail(diagnostic)


def update_diagnostic_section(arguments):
    diagnostic_id = arguments.get('diagnostic_id')
    section_id = arguments.get('section_id')
    section = DiagnosticSection.objects.select_related('diagnostic').filter(
        pk=section_id, diagnostic_id=diagnostic_id,
    ).first()
    if section is None:
        raise ToolError(f'No existe la sección id={section_id} en el diagnóstico id={diagnostic_id}.')
    data = {k: v for k, v in arguments.items() if k not in ('diagnostic_id', 'section_id')}
    serializer = DiagnosticSectionUpdateSerializer(section, data=data, partial=True)
    if not serializer.is_valid():
        raise ToolError(_serializer_errors_to_message(serializer.errors))
    serializer.save()
    diagnostic_service.log_change(
        section.diagnostic,
        change_type=DiagnosticChangeLog.ChangeType.SECTION_UPDATED,
        field_name=section.section_type,
        description=f'Sección «{section.title}» actualizada (vía MCP).',
        actor_type=DiagnosticChangeLog.ActorType.SELLER,
    )
    return DiagnosticSectionSerializer(section).data


def bulk_update_diagnostic_sections(arguments):
    diagnostic = _get_diagnostic_or_error(arguments.get('diagnostic_id'))
    payload = arguments.get('sections') or []
    if not isinstance(payload, list):
        raise ToolError('sections debe ser una lista de {id, ...campos}.')
    updated_ids = []
    for entry in payload:
        if not isinstance(entry, dict) or 'id' not in entry:
            continue
        section = DiagnosticSection.objects.filter(
            pk=entry['id'], diagnostic_id=diagnostic.id,
        ).first()
        if section is None:
            continue
        serializer = DiagnosticSectionUpdateSerializer(section, data=entry, partial=True)
        if serializer.is_valid():
            serializer.save()
            updated_ids.append(section.id)
    if updated_ids:
        diagnostic_service.log_change(
            diagnostic,
            change_type=DiagnosticChangeLog.ChangeType.SECTION_UPDATED,
            description=f'{len(updated_ids)} secciones actualizadas en bloque (vía MCP).',
            actor_type=DiagnosticChangeLog.ActorType.SELLER,
        )
    return _detail(diagnostic)


def update_diagnostic_status(arguments):
    diagnostic = _get_diagnostic_or_error(arguments.get('diagnostic_id'))
    new_status = arguments.get('status')
    valid = {s.value for s in WebAppDiagnostic.Status}
    if new_status not in valid:
        raise ToolError(f'status inválido: usa uno de {sorted(valid)}.')
    try:
        diagnostic_service.transition_status(
            diagnostic, new_status,
            actor_type=DiagnosticChangeLog.ActorType.SELLER,
        )
    except ValueError as exc:
        raise ToolError(f'Transición no permitida: {exc}')
    return _detail(diagnostic)


def _send(diagnostic, kind):
    from content.services.diagnostic_email_service import DiagnosticEmailService
    if kind == 'initial':
        target = WebAppDiagnostic.Status.SENT
        email_fn = DiagnosticEmailService.send_initial_to_client
    else:
        target = WebAppDiagnostic.Status.SENT
        email_fn = DiagnosticEmailService.send_final_to_client
    try:
        diagnostic_service.transition_status(
            diagnostic, target, actor_type=DiagnosticChangeLog.ActorType.SELLER,
        )
    except ValueError as exc:
        raise ToolError(f'No se puede enviar ({kind}): {exc}')
    try:
        email_ok = email_fn(diagnostic)
    except Exception:
        email_ok = False
    if email_ok:
        diagnostic_service.log_change(
            diagnostic,
            change_type=DiagnosticChangeLog.ChangeType.EMAIL_SENT,
            description=f'Email «{kind}» enviado al cliente (vía MCP).',
            actor_type=DiagnosticChangeLog.ActorType.SYSTEM,
        )
    payload = _detail(diagnostic)
    payload['email_ok'] = bool(email_ok)
    return payload


def send_initial(arguments):
    return _send(_get_diagnostic_or_error(arguments.get('diagnostic_id')), 'initial')


def send_final(arguments):
    return _send(_get_diagnostic_or_error(arguments.get('diagnostic_id')), 'final')


def mark_in_analysis(arguments):
    diagnostic = _get_diagnostic_or_error(arguments.get('diagnostic_id'))
    try:
        diagnostic_service.transition_status(
            diagnostic, WebAppDiagnostic.Status.NEGOTIATING,
            actor_type=DiagnosticChangeLog.ActorType.SELLER,
        )
    except ValueError as exc:
        raise ToolError(f'Transición no permitida: {exc}')
    return _detail(diagnostic)


def delete_diagnostic(arguments):
    diagnostic = _get_diagnostic_or_error(arguments.get('diagnostic_id'))
    diag_id = diagnostic.id
    diagnostic.delete()
    return {'deleted': True, 'id': diag_id}


def list_diagnostic_templates(arguments):
    items = [info for slug, meta in TEMPLATES.items() if (info := _stat(slug, meta)) is not None]
    return {'results': items}


def get_diagnostic_template(arguments):
    slug = arguments.get('slug')
    meta = TEMPLATES.get(slug)
    if meta is None:
        raise ToolError(f'No existe la plantilla "{slug}". Usa list_diagnostic_templates.')
    path = TEMPLATES_DIR / meta['filename']
    try:
        content = path.read_text(encoding='utf-8')
        stat = path.stat()
    except (FileNotFoundError, OSError):
        raise ToolError('El archivo de la plantilla no está disponible en el servidor.')

    diagnostic_id = arguments.get('diagnostic_id')
    if diagnostic_id:
        from content.services.diagnostic_service import build_render_context
        from content.views.diagnostic_template import _apply_render_context
        diagnostic = WebAppDiagnostic.objects.filter(pk=diagnostic_id).first()
        if diagnostic is None:
            raise ToolError(f'No existe un diagnóstico con id={diagnostic_id}.')
        pending = '*[pendiente de definir — configura este valor en el tab General del diagnóstico]*'
        ctx = build_render_context(diagnostic)
        for key in ('investment_amount', 'duration_label'):
            if not ctx.get(key):
                ctx[key] = pending
        content = _apply_render_context(content, ctx)

    from datetime import datetime, timezone as dt_timezone
    return {
        'slug': slug,
        'title': meta['title'],
        'filename': meta['filename'],
        'updated_at': datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc).isoformat(),
        'content_markdown': content,
    }


# ── Registry ─────────────────────────────────────────────────────────────────

_DIAG_ID_PROP = {'diagnostic_id': {'type': 'integer', 'description': 'ID del diagnóstico.'}}
_STATUS_ENUM = [s.value for s in WebAppDiagnostic.Status]

_SECTION_WRITE_PROPS = {
    'title': {'type': 'string'},
    'order': {'type': 'integer'},
    'is_enabled': {'type': 'boolean'},
    'visibility': {'type': 'string'},
    'content_json': open_object(
        'Contenido JSON de la sección, según su tipo.',
        'Cada tipo de sección tiene su propio contenido validado por el serializer del Panel.',
    ),
}

DIAGNOSTIC_TOOLS = close_root_schemas([
    {
        'name': 'list_diagnostics',
        'description': 'Lista diagnósticos. Filtros: status, client (client_id).',
        'input_schema': {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'enum': _STATUS_ENUM},
                'client': {'type': 'integer', 'description': 'client_id.'},
            },
        },
        'handler': list_diagnostics,
    },
    {
        'name': 'get_diagnostic',
        'description': 'Devuelve un diagnóstico completo (secciones, adjuntos, historial, transiciones).',
        'input_schema': {'type': 'object', 'properties': _DIAG_ID_PROP, 'required': ['diagnostic_id']},
        'handler': get_diagnostic,
    },
    {
        'name': 'create_diagnostic',
        'description': (
            'Crea un diagnóstico para un cliente existente (siembra 8 secciones). '
            'Requiere client_id; opcionales language (es/en) y title.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'client_id': {'type': 'integer'},
                'language': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'},
                'title': {'type': 'string'},
            },
            'required': ['client_id'],
        },
        'handler': create_diagnostic,
    },
    {
        'name': 'update_diagnostic',
        'description': (
            'Actualiza datos generales (parcial): title, slug, language, expires_at, '
            'client_id, investment_amount, '
            'currency, payment_terms, duration_label, size_category, radiography, y '
            'datos de cliente (client_name/email/phone/company, propagate_client_updates).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DIAG_ID_PROP,
                'title': {'type': 'string'},
                'slug': {'type': 'string'},
                'language': {'type': 'string', 'enum': ['es', 'en']},
                'expires_at': {
                    'type': ['string', 'null'],
                    'description': 'Fecha-hora ISO de expiración o null.',
                },
                'client_id': {
                    'type': ['integer', 'null'],
                    'description': 'ID del perfil de cliente asociado.',
                },
                'investment_amount': {'type': ['number', 'string', 'null']},
                'currency': {'type': 'string', 'enum': ['COP', 'USD']},
                'payment_terms': open_object(
                    'Condiciones de pago del diagnóstico.',
                    'El Panel guarda condiciones de pago configurables como JSON libre.',
                ),
                'duration_label': {'type': 'string'},
                'size_category': {'type': 'string', 'enum': ['small', 'medium', 'large']},
                'radiography': open_object(
                    'Radiografía técnica del diagnóstico.',
                    'La radiografía conserva claves variables según la aplicación diagnosticada.',
                ),
                'client_name': {'type': 'string'},
                'client_email': {'type': 'string'},
                'client_phone': {'type': 'string'},
                'client_company': {'type': 'string'},
                'propagate_client_updates': {'type': 'boolean'},
            },
            'required': ['diagnostic_id'],
        },
        'handler': update_diagnostic,
    },
    {
        'name': 'update_diagnostic_section',
        'description': (
            'Actualiza una sección (parcial): title, order, is_enabled, '
            'visibility, content_json. Envía diagnostic_id y section_id.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DIAG_ID_PROP,
                'section_id': {'type': 'integer'},
                **_SECTION_WRITE_PROPS,
            },
            'required': ['diagnostic_id', 'section_id'],
        },
        'handler': update_diagnostic_section,
    },
    {
        'name': 'bulk_update_diagnostic_sections',
        'description': (
            'Actualiza varias secciones en una llamada. sections = lista de '
            '{id, ...campos}; si se omite, devuelve el diagnóstico sin cambios.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DIAG_ID_PROP,
                'sections': {
                    'type': 'array',
                    'items': closed_object(
                        {'id': {'type': 'integer'}, **_SECTION_WRITE_PROPS},
                        ['id'],
                    ),
                },
            },
            'required': ['diagnostic_id'],
        },
        'handler': bulk_update_diagnostic_sections,
    },
    {
        'name': 'update_diagnostic_status',
        'description': (
            'Cambia el estado del diagnóstico respetando las transiciones '
            'permitidas (draft→sent, sent→negotiating/accepted/rejected, etc.).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_DIAG_ID_PROP, 'status': {'type': 'string', 'enum': _STATUS_ENUM}},
            'required': ['diagnostic_id', 'status'],
        },
        'handler': update_diagnostic_status,
    },
    {
        'name': 'send_initial',
        'description': 'Transiciona a SENT y envía el documento inicial al cliente por email.',
        'input_schema': {'type': 'object', 'properties': _DIAG_ID_PROP, 'required': ['diagnostic_id']},
        'handler': send_initial,
    },
    {
        'name': 'send_final',
        'description': 'Transiciona a SENT (final, con pricing) y envía el documento final por email.',
        'input_schema': {'type': 'object', 'properties': _DIAG_ID_PROP, 'required': ['diagnostic_id']},
        'handler': send_final,
    },
    {
        'name': 'mark_in_analysis',
        'description': 'Transición manual SENT → NEGOTIATING (cliente autorizó el análisis).',
        'input_schema': {'type': 'object', 'properties': _DIAG_ID_PROP, 'required': ['diagnostic_id']},
        'handler': mark_in_analysis,
    },
    {
        'name': 'list_diagnostic_templates',
        'description': 'Lista las plantillas markdown estáticas disponibles.',
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': list_diagnostic_templates,
    },
    {
        'name': 'get_diagnostic_template',
        'description': (
            'Devuelve el markdown de una plantilla. Con diagnostic_id opcional '
            'interpola los datos del diagnóstico en los placeholders.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'slug': {'type': 'string', 'description': 'diagnostico-aplicacion | diagnostico-tecnico | anexo.'},
                'diagnostic_id': {'type': 'integer'},
            },
            'required': ['slug'],
        },
        'handler': get_diagnostic_template,
    },
    {
        'name': 'delete_diagnostic',
        'description': (
            'Elimina permanentemente un diagnóstico por ID, junto con sus '
            'secciones dependientes, siguiendo la misma regla del panel.'
        ),
        'input_schema': {'type': 'object', 'properties': _DIAG_ID_PROP, 'required': ['diagnostic_id']},
        'handler': delete_diagnostic,
    },
])
