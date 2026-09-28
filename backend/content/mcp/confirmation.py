import hashlib
import json
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from content.mcp.context import bypass_confirmation, current_mcp_context
from content.models import McpActionIntent, McpCredential


INTENT_TTL_MINUTES = 10


def canonical_arguments_hash(arguments):
    encoded = json.dumps(
        arguments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def preview_sensitive_action(tool, arguments):
    from content.mcp.protocol import ToolError

    context = current_mcp_context()
    if context is None or context.credential is None:
        raise ToolError(
            'La acción sensible requiere una credencial MCP identificable.',
            code='FORBIDDEN',
        )
    prepare_arguments = tool.get('prepare_arguments')
    if prepare_arguments:
        arguments = prepare_arguments(arguments)
    impact_builder = tool.get('impact_builder')
    impact = impact_builder(arguments) if impact_builder else {
        'summary': tool.get('confirmation_message') or tool['description'],
        'tool': tool['name'],
        'arguments': arguments,
    }
    etag_resolver = tool.get('etag_resolver')
    resource_etags = etag_resolver(arguments) if etag_resolver else {}
    intent = McpActionIntent.objects.create(
        connector=context.connector,
        credential=context.credential,
        tool_name=tool['name'],
        arguments=arguments,
        arguments_hash=canonical_arguments_hash(arguments),
        impact=impact,
        resource_etags=resource_etags,
        expires_at=timezone.now() + timedelta(minutes=INTENT_TTL_MINUTES),
    )
    return {
        'confirmation_required': True,
        'confirmation_id': str(intent.id),
        'expires_at': intent.expires_at.isoformat(),
        'impact': impact,
    }


def confirm_action(arguments, tools):
    from content.mcp.protocol import ToolError

    context = current_mcp_context()
    expired = False
    if context is None or context.credential is None:
        raise ToolError('No existe contexto de credencial.', code='FORBIDDEN')
    try:
        confirmation_id = str(uuid.UUID(str(arguments.get('confirmation_id'))))
    except (AttributeError, ValueError) as exc:
        raise ToolError(
            'No existe esa confirmación para este conector.',
            code='NOT_FOUND',
        ) from exc
    try:
        with transaction.atomic():
            intent = (
                McpActionIntent.objects.select_for_update()
                .get(pk=confirmation_id, connector=context.connector)
            )
            if intent.credential_id != context.credential.id:
                raise ToolError(
                    'La confirmación pertenece a otra credencial.',
                    code='FORBIDDEN',
                )
            tool = next(
                (candidate for candidate in tools if candidate['name'] == intent.tool_name),
                None,
            )
            if tool is None or not tool.get('requires_confirmation'):
                raise ToolError('La herramienta confirmada ya no está disponible.', code='CONFLICT')
            credential = McpCredential.objects.select_for_update().get(pk=context.credential.pk)
            if not credential.is_usable or not credential.allows(tool['name']):
                raise ToolError('La credencial no permite esta herramienta.', code='FORBIDDEN')
            if intent.status == McpActionIntent.STATUS_EXECUTED:
                return {
                    'confirmed': True,
                    'replayed': True,
                    'result': (
                        {'delivered': True, 'content_available': False, 'new_confirmation_required': True}
                        if tool.get('ephemeral_result') else intent.result
                    ),
                }
            if intent.status != McpActionIntent.STATUS_PENDING:
                raise ToolError(
                    'La confirmación ya no está disponible.',
                    code='CONFIRMATION_EXPIRED',
                )
            if intent.expires_at <= timezone.now():
                intent.status = McpActionIntent.STATUS_EXPIRED
                intent.save(update_fields=['status'])
                expired = True
            else:
                if canonical_arguments_hash(intent.arguments) != intent.arguments_hash:
                    raise ToolError(
                        'La carga de la confirmación no conserva su huella.',
                        code='CONFLICT',
                    )
                etag_resolver = tool.get('etag_resolver')
                if etag_resolver:
                    current_etags = etag_resolver(intent.arguments)
                    if current_etags != intent.resource_etags:
                        raise ToolError(
                            'Los recursos cambiaron desde la vista previa.',
                            code='STALE_VERSION',
                            details={
                                'expected': intent.resource_etags,
                                'current': current_etags,
                            },
                        )
                with bypass_confirmation():
                    result = tool['handler'](dict(intent.arguments))
                intent.status = McpActionIntent.STATUS_EXECUTED
                intent.executed_at = timezone.now()
                intent.result = (
                    {'delivered': True, 'content_available': False, 'new_confirmation_required': True}
                    if tool.get('ephemeral_result') else result
                )
                intent.save(update_fields=['status', 'executed_at', 'result'])
    except McpActionIntent.DoesNotExist as exc:
        raise ToolError(
            'No existe esa confirmación para este conector.',
            code='NOT_FOUND',
        ) from exc
    if expired:
        raise ToolError(
            'La confirmación expiró; genera una vista previa nueva.',
            code='CONFIRMATION_EXPIRED',
        )
    return {'confirmed': True, 'replayed': False, 'result': result}


def cancel_action(arguments):
    from content.mcp.protocol import ToolError

    context = current_mcp_context()
    if context is None or context.credential is None:
        raise ToolError('No existe contexto de credencial.', code='FORBIDDEN')
    confirmation_id = arguments.get('confirmation_id')
    updated = McpActionIntent.objects.filter(
        pk=confirmation_id,
        connector=context.connector,
        credential=context.credential,
        status=McpActionIntent.STATUS_PENDING,
    ).update(status=McpActionIntent.STATUS_CANCELLED)
    if not updated:
        raise ToolError(
            'No existe una confirmación pendiente con ese id.',
            code='NOT_FOUND',
        )
    return {'cancelled': True, 'confirmation_id': str(confirmation_id)}
