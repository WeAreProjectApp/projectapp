"""Measured, version-specific calibration without automatic repricing."""
from decimal import Decimal
from statistics import median

from content.models import (
    CalculatorActual,
    CalculatorEstimate,
    CalculatorRevision,
    ProjectCalculatorVersion,
)
from content.services.requirement_calculator import digest
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError


@transaction.atomic
def record_estimate(data, *, actor):
    values = dict(data)
    expected_digest = values.pop('definition_digest')
    for key, default in [('project_id', None), ('project_version_id', None), ('expected_size', '')]:
        values.setdefault(key, default)
    revision = get_object_or_404(CalculatorRevision, pk=values['revision_id'])
    project_version_id = values.get('project_version_id')
    if project_version_id:
        version = get_object_or_404(ProjectCalculatorVersion, pk=project_version_id,
                                     project_id=values.get('project_id'), base_revision=revision)
        config = version.definition
    else:
        config = revision.definition
    if digest(config) != expected_digest:
        raise ValidationError('La definición utilizada cambió; consulta sus parámetros antes de registrar.')
    if values.get('project_id'):
        from accounts.models import Project
        get_object_or_404(Project, pk=values['project_id'])
    signals = {row['id']: row for row in config['signals']}
    if not set(values['signal_ids']) <= signals.keys():
        raise ValidationError('Hay señales que no pertenecen a esta versión.')
    if values['size'] != 'PROJECT' and not values['signal_ids']:
        raise ValidationError('Incluye una señal aplicable para explicar la talla.')
    estimate, created = CalculatorEstimate.objects.get_or_create(
        request_id=values['request_id'],
        defaults={**values, 'snapshot': config, 'definition_digest': expected_digest, 'author': actor},
    )
    if not created and (estimate.author_id != getattr(actor, 'pk', None) or estimate.definition_digest != expected_digest
                        or any(getattr(estimate, key) != value for key, value in values.items())):
        raise ValidationError('Ese identificador ya corresponde a otra estimación.')
    return {'id': estimate.pk, 'size': estimate.size, 'package_eligible': estimate.size != 'PROJECT',
            'revision_id': estimate.revision_id,
            'project_version_id': estimate.project_version_id}


@transaction.atomic
def record_actual(data, *, actor):
    estimate = get_object_or_404(CalculatorEstimate.objects.select_for_update(), pk=data['estimate_id'])
    values = dict(data)
    previous_id = values.get('supersedes_id')
    previous = estimate.actuals.filter(correction__isnull=True).first()
    if (previous is not None and previous.pk != previous_id) or (previous is None and previous_id is not None):
        raise ValidationError('Indica el último cierre como supersedes_id para registrar una corrección.')
    values.setdefault('hourly_cost_cop', estimate.snapshot['calibration']['hourly_cost_cop'])
    event = CalculatorActual.objects.create(**values, author=actor)
    return {'id': event.pk, 'estimate_id': estimate.pk, 'supersedes_id': event.supersedes_id}


def _clip(value, maximum):
    return value.encode('utf-8')[:maximum].decode('utf-8', errors='ignore')


def _actual_payload(event, *, summary=False):
    return {'id': event.pk, 'actual_hours': str(event.actual_hours),
            'hourly_cost_cop': str(event.hourly_cost_cop) if event.hourly_cost_cop is not None else None,
            'evidence': _clip(event.evidence, 128) if summary else event.evidence,
            'cause': _clip(event.cause, 128) if summary else event.cause,
            'supersedes_id': event.supersedes_id, 'author_id': event.author_id,
            'created_at': event.created_at.isoformat()}


def _estimate_payload(row, *, summary=False):
    return {'id': row.pk, 'requirement': _clip(row.requirement, 320) if summary else row.requirement,
            'size': row.size, 'explanation': _clip(row.explanation, 320) if summary else row.explanation,
            'project_id': row.project_id, 'project_name': (_clip(row.project.name, 200) if summary else row.project.name) if row.project else None,
            'revision_id': row.revision_id, 'project_version_id': row.project_version_id,
            'definition_digest': row.definition_digest, 'request_id': str(row.request_id),
            'author_id': row.author_id, 'created_at': row.created_at.isoformat(),
            'signal_ids': row.signal_ids[:3] if summary else row.signal_ids, 'expected_size': row.expected_size}


def estimates(*, limit=20, offset=0):
    if not 1 <= limit <= 50 or offset < 0:
        raise ValidationError('Usa limit entre 1 y 50 y offset no negativo.')
    queryset = (CalculatorEstimate.objects.select_related('project').defer('snapshot')
        .annotate(actual_count=Count('actuals'))
        .prefetch_related(Prefetch('actuals', queryset=CalculatorActual.objects.order_by('-pk')[:3], to_attr='recent_actuals')))
    return {'count': queryset.count(), 'results': [
        {**_estimate_payload(row, summary=True), 'is_summary': True, 'actual_count': row.actual_count,
         'actuals': [_actual_payload(event, summary=True) for event in row.recent_actuals]}
        for row in queryset[offset:offset + limit]]}


def estimate_detail(estimate_id):
    row = get_object_or_404(CalculatorEstimate.objects.select_related('project').defer('snapshot'), pk=estimate_id)
    return _estimate_payload(row)


def actual_history(estimate_id, *, limit=3, offset=0):
    if not 1 <= limit <= 3 or offset < 0:
        raise ValidationError('Usa limit entre 1 y 3 y offset no negativo.')
    get_object_or_404(CalculatorEstimate.objects.only('pk'), pk=estimate_id)
    rows = CalculatorActual.objects.filter(estimate_id=estimate_id)
    return {'count': rows.count(), 'results': [_actual_payload(row) for row in rows[offset:offset + limit]]}


def report(*, limit=20, offset=0):
    if not 1 <= limit <= 50 or offset < 0:
        raise ValidationError('Usa limit entre 1 y 50 y offset no negativo.')
    # Cohorts are separated by effective definition, including negotiated parameters.
    groups = {}
    queryset = CalculatorActual.objects.filter(correction__isnull=True).values(
        'actual_hours', 'hourly_cost_cop', 'estimate__definition_digest', 'estimate__size',
        'estimate__revision_id', 'estimate__snapshot__sizes', 'estimate__snapshot__calibration',
    )
    for actual in queryset.iterator(chunk_size=100):
        key = (actual['estimate__definition_digest'], actual['estimate__size'])
        band = next((value for value in actual['estimate__snapshot__sizes'] if value['id'] == actual['estimate__size']), None)
        if band is None:
            continue
        group = groups.setdefault(key, {'band': {field: band[field] for field in ('hours_min', 'hours_max', 'standard_value_cop')},
            'rule': actual['estimate__snapshot__calibration'], 'revision_id': actual['estimate__revision_id'],
            'hours': [], 'costs': []})
        group['hours'].append(actual['actual_hours'])
        if actual['hourly_cost_cop'] is not None:
            group['costs'].append(actual['actual_hours'] * actual['hourly_cost_cop'])
    results = []
    for (definition_digest, size), group in groups.items():
        rule = group['rule']
        band = group['band']
        real = median(group['hours'])
        low, high = Decimal(band['hours_min']), Decimal(band['hours_max'])
        deviation = ((real - high) / high * 100 if real > high else
                     (real - low) / low * 100 if real < low and low else Decimal(0))
        enough = len(group['hours']) >= rule['minimum_samples']
        costs = group['costs']
        cost = median(costs) if costs else None
        value = Decimal(band['standard_value_cop']) if band['standard_value_cop'] is not None else None
        deficit = ((cost - value) / value * 100) if cost is not None and value else None
        results.append({'definition_digest': definition_digest, 'revision_id': group['revision_id'],
                        'size': size, 'samples': len(group['hours']), 'cost_samples': len(costs),
                        'minimum_samples': rule['minimum_samples'],
                        'status': 'measured' if enough else 'insufficient_data',
                        'median_hours': str(real), 'deviation_percent': str(round(deviation, 2)),
                        'median_cost_cop': str(cost) if cost is not None else None,
                        'standard_value_cop': str(value) if value is not None else None,
                        'covers_median_cost': value >= cost if value is not None and cost is not None else None,
                        'propose_review': enough and (abs(deviation) > Decimal(rule['deviation_percent']) or
                            (len(costs) >= rule['minimum_samples'] and deficit is not None and deficit > Decimal(rule['deviation_percent'])))})
    references = CalculatorEstimate.objects.exclude(expected_size='')
    from django.db.models import F
    return {'count': len(results), 'cohorts': results[offset:offset + limit], 'provisional': not results or any(
                row['status'] == 'insufficient_data' or row['cost_samples'] < row['minimum_samples']
                or row['standard_value_cop'] is None for row in results),
            'consistency': {'reviewed': references.count(), 'disagreements': references.exclude(size=F('expected_size')).count()},
            'note': 'Muestras por definición efectiva y talla. Los cierres corregidos se conservan y sólo su último evento alimenta la medición. Las alertas no cambian precios ni reglas.'}
