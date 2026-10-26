from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.services.panel_dashboard_service import build_panel_dashboard


@api_view(['GET'])
@permission_classes([IsAdminUser])
def panel_dashboard(request):
    """Consolidated KPIs for the global panel dashboard.

    Finance data is superuser-only; other admins receive ``finance: null``
    and no finance-derived attention items.
    """
    return Response(
        build_panel_dashboard(include_finance=request.user.is_superuser)
    )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def dashboard_attention(request, kind, record_id=None):
    """Read current radar records without exposing financial data to staff."""
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    from content.services.dashboard_attention_service import (
        TYPES, attention_records, record_count, record_model, record_payload,
    )
    from content.utils import today_bogota

    if kind not in TYPES:
        return Response({'detail': 'Tipo de alerta no encontrado.'}, status=404)
    if kind == 'recurring_due' and not request.user.is_superuser:
        return Response({'detail': 'No tienes permiso para consultar estos pagos.'}, status=403)
    today, now = today_bogota(), timezone.now()
    records = attention_records(kind, today, now)
    if record_id is not None:
        obj = get_object_or_404(record_model(kind), pk=record_id)
        if kind == 'emails_failed' and obj.delivery_role != obj.DeliveryRole.PRIMARY:
            return Response({'detail': 'Envío no encontrado.'}, status=404)
        if isinstance(records, list):
            eligible = any((row['id'] if isinstance(row, dict) else row.pk) == record_id for row in records)
        else:
            eligible = records.filter(pk=record_id).exists()
        return Response({**record_payload(kind, obj, today), 'eligible': eligible})
    try:
        page = int(request.query_params.get('page', 1))
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return Response({'detail': 'La página debe ser un entero positivo.'}, status=400)
    total = record_count(records)
    offset = (page - 1) * 5
    selected = list(records[offset:offset + 5])
    if kind == 'emails_failed':
        from content.models import EmailLog
        from content.services.email_log_service import attach_delivery_recipients
        ids = [row['id'] for row in selected]
        hydrated = {obj.pk: obj for obj in attach_delivery_recipients(
            EmailLog.objects.filter(pk__in=ids).select_related('snapshot'),
        )}
        selected = [hydrated[pk] for pk in ids if pk in hydrated]
    return Response({
        'results': [record_payload(kind, obj, today) for obj in selected],
        'total': total, 'page': page, 'page_size': 5,
        'has_next': offset + 5 < total,
    })
