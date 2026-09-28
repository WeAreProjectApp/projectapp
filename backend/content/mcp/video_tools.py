"""Video tools consume completed binary uploads without copying them into RAM."""
from django.db import transaction
from django.core.files import File
from django.utils import timezone
from rest_framework.exceptions import APIException

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import consume_upload
from content.models import BusinessProposal, McpUpload
from content.services.video_resource_service import resource_payload, update_resource


def _target(arguments, module, personalized):
    language = arguments.get('language', 'es')
    proposal = None
    if personalized:
        try:
            proposal = BusinessProposal.objects.get(pk=int(arguments.get('proposal_id')))
        except (BusinessProposal.DoesNotExist, ValueError, TypeError) as exc:
            raise ToolError('No existe esa propuesta.', code='NOT_FOUND') from exc
        language = proposal.language
    return module, language, proposal


def _execute(arguments, module, personalized, action):
    module, language, proposal = _target(arguments, module, personalized)
    try:
        if action == 'get':
            return resource_payload(module, language, proposal)
        with transaction.atomic():
            upload = None
            if action == 'upload':
                upload = consume_upload(arguments.get('asset_id'), allowed_content_types={'video/mp4'})
            if upload is None:
                return update_resource(
                    module, language, proposal=proposal, actor=mcp_actor(),
                    revision=arguments.get('revision'), action=action,
                )
            with upload.file.open('rb') as source:
                result = update_resource(
                    module, language, proposal=proposal, actor=mcp_actor(),
                    revision=arguments.get('revision'), action=action, uploaded_file=File(source, name=upload.filename),
                )
            upload.status = McpUpload.STATUS_CONSUMED
            upload.consumed_at = timezone.now()
            upload.save(update_fields=['status', 'consumed_at', 'updated_at'])
            # Permanent storage owns its own copy; temporary bytes are no longer needed.
            transaction.on_commit(lambda: upload.file.delete(save=False))
            return result
    except APIException as exc:
        raise ToolError(
            str(exc.detail), code='CONFLICT' if exc.status_code == 409 else 'VALIDATION_ERROR',
            details={'fields': exc.detail},
        ) from exc


def _set_visibility(arguments, module):
    from content.models import ExplainerVideoSettings
    from content.serializers.explainer_videos import ExplainerVideoSettingsSerializer
    from content.services.explainer_video_service import MODULE_SWITCHES
    from content.services.frontend_build import schedule_rebuild_after_publish
    field = MODULE_SWITCHES[module]
    if not isinstance(arguments.get('visible'), bool):
        raise ToolError('visible debe ser true o false.')
    serializer = ExplainerVideoSettingsSerializer(ExplainerVideoSettings.load(), data={field: arguments['visible']}, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if module != 'proposal':
        schedule_rebuild_after_publish()
    return {'visible': arguments['visible']}


def video_tools(module, *, personalized=False):
    prefix = 'proposal_personalized' if personalized else {
        'proposal': 'proposal_generic', 'financing': 'partnership_program',
        'additional-modules': 'additional_modules',
    }[module]
    target = {'proposal_id': {'type': 'integer', 'minimum': 1}} if personalized else {
        'language': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'},
    }
    tools = []
    actions = [('get', 'get'), ('upload', 'set'), ('remove', 'remove')]
    if not personalized:
        actions.append(('restore-default', 'restore_default'))
    for action, verb in actions:
        properties = dict(target)
        required = ['proposal_id'] if personalized else []
        if action != 'get':
            properties['revision'] = {'type': 'integer', 'minimum': 0, 'description': 'Revisión obtenida al consultar el recurso.'}
            required.append('revision')
        if action == 'upload':
            properties['asset_id'] = {'type': 'string', 'format': 'uuid'}
            required.append('asset_id')
        descriptions = {
            'get': 'Consulta el video vigente, su revisión y el límite de carga.',
            'upload': 'Carga o sustituye el video usando un asset_id MP4 completo. Primero begin_upload, PUT firmado o upload_asset_chunk y complete_upload. Hasta 250 MB; conserva el anterior si falla.',
            'remove': 'Quita el video. No restaura automáticamente el predeterminado.',
            'restore-default': 'Restaura explícitamente el video genérico incluido con la aplicación.',
        }
        tools.append({
            'name': f'{verb}_{prefix}_video', 'description': descriptions[action],
            'risk': 'read' if action == 'get' else 'sensitive' if action == 'remove' else 'write',
            'requires_confirmation': action == 'remove',
            'confirmation_message': descriptions[action],
            'input_schema': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False},
            'handler': lambda arguments, action=action: _execute(arguments, module, personalized, action),
        })
    if not personalized:
        tools.append({
            'name': f'set_{prefix}_video_visibility',
            'description': 'Muestra u oculta el video general en las vistas públicas de este módulo.',
            'risk': 'write',
            'input_schema': {'type': 'object', 'properties': {'visible': {'type': 'boolean'}}, 'required': ['visible'], 'additionalProperties': False},
            'handler': lambda arguments: _set_visibility(arguments, module),
        })
    return tools


PROPOSAL_VIDEO_TOOLS = video_tools('proposal') + video_tools('proposal', personalized=True)
