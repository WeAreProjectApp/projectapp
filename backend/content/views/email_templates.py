import logging

from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import EmailTemplateConfig
from content.serializers.proposal import EmailTemplateConfigSerializer
from content.services.email_template_registry import (
    get_all_keys,
    get_default_field_values,
    get_template_entry,
    resolve_field_values,
    substitute_variables,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def email_template_list(request):
    """
    GET — List all 23 email templates with metadata and customization status.

    Returns a list of dicts, each containing registry metadata plus
    current ``is_active`` and ``is_customized`` flags from the DB.
    """
    all_keys = get_all_keys()
    db_configs = {
        c.template_key: c
        for c in EmailTemplateConfig.objects.filter(template_key__in=all_keys)
    }

    result = []
    for key in all_keys:
        entry = get_template_entry(key)
        if not entry:
            continue
        db_config = db_configs.get(key)
        result.append({
            'template_key': key,
            'name': entry['name'],
            'description': entry['description'],
            'category': entry['category'],
            'is_active': db_config.is_active if db_config else True,
            'is_customized': bool(
                db_config and db_config.content_overrides
            ),
            'editable_fields_count': len(entry.get('editable_fields', [])),
        })

    return Response(result)


@api_view(['GET', 'PUT'])
@permission_classes([IsAdminUser])
def email_template_detail(request, template_key):
    """
    GET — Retrieve a single template's editable fields with current values.
    PUT — Save content overrides and/or is_active flag.
    """
    entry = get_template_entry(template_key)
    if not entry:
        return Response(
            {'detail': f'La plantilla "{template_key}" no existe en el registro.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    db_config = EmailTemplateConfig.objects.filter(
        template_key=template_key,
    ).first()

    if request.method == 'GET':
        defaults = get_default_field_values(template_key)
        overrides = db_config.content_overrides if db_config else {}

        fields_with_values = []
        for field_def in entry.get('editable_fields', []):
            key = field_def['key']
            fields_with_values.append({
                **field_def,
                'current_value': overrides.get(key, ''),
                'default_value': defaults.get(key, ''),
                'is_overridden': key in overrides and bool(overrides[key]),
            })

        return Response({
            'template_key': template_key,
            'name': entry['name'],
            'description': entry['description'],
            'category': entry['category'],
            'is_active': db_config.is_active if db_config else True,
            'is_customized': bool(overrides),
            'available_variables': entry.get('available_variables', []),
            'editable_fields': fields_with_values,
            **({'text_formats': db_config.text_formats} if db_config and db_config.text_formats else {}),
        })

    # PUT — save overrides
    content_overrides = request.data.get('content_overrides', {})
    is_active = request.data.get('is_active', True)

    if not isinstance(content_overrides, dict):
        return Response(
            {'detail': 'content_overrides debe ser un objeto (dict).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate field keys against registry
    valid_keys = {
        f['key'] for f in entry.get('editable_fields', [])
    }
    invalid_keys = set(content_overrides.keys()) - valid_keys
    if invalid_keys:
        return Response(
            {'detail': f'Claves de campo no válidas: {invalid_keys}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Strip empty values from overrides
    cleaned = {k: v for k, v in content_overrides.items() if v}
    from content.services.editorial_format import validate_formats
    text_formats = validate_formats('emailtemplateconfig', {'content_overrides': cleaned}, request.data.get('text_formats', getattr(db_config, 'text_formats', {})))

    if db_config:
        db_config.content_overrides = cleaned
        db_config.text_formats = text_formats
        db_config.is_active = is_active
        db_config.save(update_fields=['content_overrides', 'text_formats', 'is_active', 'updated_at'])
    else:
        db_config = EmailTemplateConfig.objects.create(
            template_key=template_key,
            content_overrides=cleaned,
            text_formats=text_formats,
            is_active=is_active,
        )

    serializer = EmailTemplateConfigSerializer(db_config)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def email_template_preview(request, template_key):
    """
    GET — Render a full HTML preview of the email using sample context data.

    Merges DB overrides with defaults, substitutes variables with sample
    values, then renders the Django HTML template.
    """
    entry = get_template_entry(template_key)
    if not entry:
        return Response(
            {'detail': f'La plantilla "{template_key}" no existe en el registro.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    db_config = EmailTemplateConfig.objects.filter(
        template_key=template_key,
    ).first()
    overrides = db_config.content_overrides if db_config else {}

    # Resolve field values (merge defaults + overrides)
    field_values = resolve_field_values(template_key, overrides)
    sample_ctx = dict(entry.get('sample_context', {}))

    # Substitute {variable} placeholders in editable fields
    resolved = {}
    for key, value in field_values.items():
        resolved[key] = substitute_variables(value, sample_ctx)

    # Build template context: sample data + resolved text fields
    from content.services.editorial_email import template_formats
    template_context = {**sample_ctx, **resolved, 'editorial_formats': template_formats(db_config)}

    html_template = entry.get('html_template')
    if html_template:
        try:
            html_content = render_to_string(html_template, template_context)
        except Exception:
            logger.exception('Failed to render preview for %s', template_key)
            return Response(
                {'detail': 'No se pudo generar la vista previa de la plantilla.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    else:
        # Plain text template (contact_notification)
        body_text = resolved.get('body', '')
        subject_text = resolved.get('subject', '')
        html_content = (
            f'<html><body style="font-family:monospace;padding:20px;">'
            f'<h3>Asunto: {subject_text}</h3>'
            f'<pre style="white-space:pre-wrap;">{body_text}</pre>'
            f'</body></html>'
        )

    return Response({
        'template_key': template_key,
        'subject': resolved.get('subject', ''),
        'html_preview': html_content,
        'is_active': db_config.is_active if db_config else True,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def email_template_reset(request, template_key):
    """
    POST — Delete the DB override for a template, reverting to defaults.
    """
    entry = get_template_entry(template_key)
    if not entry:
        return Response(
            {'detail': f'La plantilla "{template_key}" no existe en el registro.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    deleted_count, _ = EmailTemplateConfig.objects.filter(
        template_key=template_key,
    ).delete()

    return Response({
        'status': 'reset',
        'deleted': deleted_count > 0,
        'template_key': template_key,
    })
