"""Shared administration boundaries for REST and MCP."""
import base64
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound, ValidationError

from procurement.filters import apply_filters
from procurement.models import Activity, Alert, Classification, Delivery, Opportunity, SavedSearch, Settings, SyncRun
from procurement.serializers import (
    AlertSerializer, AlertWriteSerializer, ClassificationSerializer, ClassificationWriteSerializer,
    DeliverySerializer, OpportunitySerializer, OpportunityListSerializer, QuerySerializer, SavedSearchSerializer,
    SavedSearchWriteSerializer, SettingsSerializer, SettingsWriteSerializer, SyncRunSerializer, validated,
)


def found(model, pk, **scope):
    try:
        return model.objects.get(pk=pk, **scope)
    except (ObjectDoesNotExist, ValueError, TypeError) as exc:
        raise NotFound('No se encontró el registro.') from exc


def page(queryset, serializer, number=1, size=25):
    count = queryset.count()
    return {'results': serializer(queryset[(number-1)*size:number*size], many=True).data,
            'count': count, 'page': number, 'page_size': size}


def opportunity_query(data, owner):
    options = validated(QuerySerializer, data)
    queryset = apply_filters(Opportunity.objects.all(), options['filters'])
    if options['classified'] or options.get('state'):
        queryset = queryset.filter(classifications__owner=owner)
        if options.get('state'):
            queryset = queryset.filter(classifications__owner=owner, classifications__state=options['state'])
    ordering = options['ordering']
    return queryset.order_by(ordering, 'pk'), options


def list_opportunities(data, owner):
    queryset, options = opportunity_query(data, owner)
    result = page(queryset.defer('description', 'source_data'), OpportunityListSerializer, options['page'], options['page_size'])
    ids = [item['id'] for item in result['results']]
    classifications = {item.opportunity_id: {'id': item.pk, 'state': item.state, 'owner': item.owner_id} for item in
                       Classification.objects.filter(opportunity_id__in=ids, owner=owner).select_related('owner')}
    for item in result['results']:
        item['my_classification'] = classifications.get(item['id'])
    return result


def detail(pk):
    opportunity = found(Opportunity, pk)
    result = dict(OpportunitySerializer(opportunity).data)
    result['classifications'] = ClassificationSerializer(
        opportunity.classifications.select_related('owner').order_by('-updated_at')[:100], many=True).data
    activities = Activity.objects.filter(classification__opportunity=opportunity).select_related('actor')[:100]
    result['activities'] = [{'id': item.pk, 'actor': item.actor.username, 'action': item.action,
                             'snapshot': item.snapshot, 'created_at': item.created_at.isoformat()} for item in activities]
    return result


@transaction.atomic
def classify(pk, data, owner, actor, *, restore=False, credential=None):
    opportunity = found(Opportunity, pk)
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    current = Classification.objects.select_for_update().filter(opportunity=opportunity, owner=owner).first()
    if restore:
        if current is None or current.state != 'discarded':
            raise ValidationError('Sólo se restaura una clasificación descartada.')
        values = {'state': current.previous_state, 'notes': current.notes}
    else:
        values = validated(ClassificationWriteSerializer, data)
    if current is None:
        current = Classification(opportunity=opportunity, owner=owner)
    if values['state'] == 'discarded' and current.state != 'discarded':
        current.previous_state = current.state
    current.state = values['state']
    current.notes = values['notes']
    current.save()
    Activity.objects.create(classification=current, actor=actor, credential=credential,
                            action='restore' if restore else 'classify',
                            snapshot={'state': current.state, 'notes': current.notes, 'owner_id': owner.pk})
    return ClassificationSerializer(current).data


@transaction.atomic
def save_search(data, owner, pk=None):
    values = validated(SavedSearchWriteSerializer, data)
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    instance = found(SavedSearch, pk, owner=owner) if pk else SavedSearch(owner=owner)
    if not pk and not values.get('name'):
        raise ValidationError({'name': 'Campo obligatorio.'})
    if values.get('is_favorite'):
        SavedSearch.objects.filter(owner=owner).exclude(pk=pk).update(is_favorite=False)
    for key, value in values.items():
        setattr(instance, key, value)
    try:
        with transaction.atomic():
            instance.save()
    except IntegrityError as exc:
        raise ValidationError({'name': 'Ya existe una búsqueda con ese nombre.'}) from exc
    return SavedSearchSerializer(instance).data


@transaction.atomic
def save_alert(data, actor, pk=None):
    values = validated(AlertWriteSerializer, data, creating=pk is None)
    instance = found(Alert, pk) if pk else Alert(created_by=actor)
    if pk:
        instance = Alert.objects.select_for_update().get(pk=pk)
        instance.version += 1
    for key, value in values.items():
        setattr(instance, key, value)
    instance.save()
    if instance.is_active:
        from procurement.tasks import evaluate_alert
        transaction.on_commit(lambda: evaluate_alert(instance.pk))
    return AlertSerializer(instance).data


@transaction.atomic
def save_settings(data):
    values = validated(SettingsWriteSerializer, data)
    Settings.current()
    settings = Settings.objects.select_for_update().get(pk=1)
    for key, value in values.items():
        setattr(settings, key, value)
    settings.save()
    return SettingsSerializer(settings).data


def filter_catalog():
    fields = {'entity_names': 'entity_name', 'departments': 'department', 'methods': 'method',
              'contract_types': 'contract_type', 'statuses': 'source_status'}
    return {key: list(Opportunity.objects.exclude(**{field: ''}).order_by(field).values_list(field, flat=True).distinct()[:500])
            for key, field in fields.items()}


def export_opportunities(data, owner):
    from openpyxl import Workbook
    queryset, _ = opportunity_query(data, owner)
    if queryset.count() > 5000:
        raise ValidationError('La exportación admite hasta 5.000 procesos. Ajusta los filtros.')
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('SECOP II')
    sheet.append(['Referencia', 'Proceso', 'Entidad', 'Departamento entidad', 'Presupuesto COP', 'Cierre Bogotá', 'URL oficial'])
    def text(value):
        value = str(value or '')
        return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
    from procurement.services.source import BOGOTA
    for item in queryset.iterator(chunk_size=250):
        closing = item.closing_at.astimezone(BOGOTA).isoformat() if item.closing_at else ''
        sheet.append([text(item.reference), text(item.title), text(item.entity_name), text(item.department),
                      item.budget, closing, text(item.source_url)])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def sync_status():
    return {'recent': SyncRunSerializer(SyncRun.objects.all()[:10], many=True).data,
            'last_success': SyncRunSerializer(SyncRun.objects.filter(status='success').first()).data
                if SyncRun.objects.filter(status='success').exists() else None,
            'open_count': apply_filters(Opportunity.objects.all(), {}).count()}
