"""Measured labor costs and explicit staff review of a versioned package corpus."""
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from content.mcp.principal import is_service_actor
from content.models import (
    CalculatorActual, CalculatorCostReview, CalculatorEstimate, CalculatorRevision, ProjectCalculatorVersion,
    RequirementCalculator,
)
from content.services.requirement_calculator import CalculatorConflict, digest, seed_definition
from content.services.requirement_package_service import SIZES


def closure_costs(data):
    """Store a precise supported total and the equivalent rate for legacy readers."""
    lines = data.get('cost_breakdown', [])
    if not lines:
        return {}
    hours = Decimal(data['actual_hours'])
    if sum(Decimal(line['hours']) for line in lines) != hours:
        raise ValidationError({'cost_breakdown': 'Las horas respaldadas deben sumar las horas reales del cierre.'})
    total = sum(Decimal(line['hours']) * Decimal(line['hourly_cost_cop']) for line in lines)
    rate = (total / hours).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    if data.get('hourly_cost_cop') is not None and Decimal(data['hourly_cost_cop']) != rate:
        raise ValidationError({'hourly_cost_cop': 'La tarifa debe coincidir con el promedio ponderado del desglose.'})
    return {'cost_breakdown': [{key: str(value) for key, value in line.items()} for line in lines],
            'verified_cost_cop': total, 'hourly_cost_cop': rate}


def _definition(definition_digest):
    if definition_digest:
        source = CalculatorRevision.objects.filter(digest=definition_digest).values_list('definition', flat=True).first()
        if source is None:
            source = ProjectCalculatorVersion.objects.filter(digest=definition_digest).values_list('definition', flat=True).first()
        if source is None:
            # An estimate keeps the definition even if its project draft has since changed.
            source = CalculatorEstimate.objects.filter(definition_digest=definition_digest).values_list('snapshot', flat=True).first()
        if source is None:
            raise NotFound('No se encontró la definición de la calculadora.')
        return definition_digest, source
    current = RequirementCalculator.objects.values_list('current_revision__digest', 'current_revision__definition').first()
    if current:
        return current
    seed = seed_definition()
    return digest(seed), seed


def _samples(definition_digest, size):
    return CalculatorActual.objects.filter(
        correction__isnull=True, estimate__definition_digest=definition_digest, estimate__size__in=size,
    ).order_by('pk').values_list('estimate__size', 'pk', 'verified_cost_cop')


def _coverage(definition_digest, band, samples, review):
    actual_ids = [pk for pk, _ in samples]
    verified = [(pk, cost) for pk, cost in samples if cost is not None]
    corpus_digest = digest([definition_digest, band['id'], actual_ids])
    cost = median([cost for _, cost in verified]) if verified else None
    standard = band['standard_value_cop']
    accepted = review is not None and review.corpus_digest == corpus_digest
    summary = {'size': band['id'], 'definition_digest': definition_digest, 'corpus_digest': corpus_digest,
               'samples': len(samples), 'verified_cost_samples': len(verified),
               'median_verified_cost_cop': str(cost) if cost is not None else None,
               'standard_value_cop': standard,
               'covers_verified_median_cost': Decimal(standard) >= cost if standard is not None and cost is not None else None,
               'economic_status': 'accepted' if accepted else 'provisional',
               'last_review': ({'id': review.pk, 'corpus_digest': review.corpus_digest, 'note': review.note,
                                'author_id': review.author_id, 'created_at': review.created_at.isoformat()}
                               if review else None)}
    return summary, {'actual_ids': actual_ids, 'verified_actual_ids': [pk for pk, _ in verified]}


def package_coverage(definition_digest=None):
    key, config = _definition(definition_digest)
    samples = {size: [] for size in SIZES}
    for size, pk, cost in _samples(key, SIZES).iterator(chunk_size=500):
        samples[size].append((pk, cost))
    latest = (CalculatorCostReview.objects.filter(definition_digest=key).order_by().values('size')
              .annotate(latest_pk=Max('pk')).values('latest_pk'))
    reviews = {row.size: row for row in CalculatorCostReview.objects.filter(pk__in=latest).defer('corpus')}
    return [_coverage(key, band, samples[band['id']], reviews.get(band['id']))[0]
            for band in config['sizes'] if band['id'] in samples]


@transaction.atomic
def accept_cost_review(data, *, actor):
    if not actor.is_active or not actor.is_staff or is_service_actor(actor):
        raise PermissionDenied('La aceptación requiere una cuenta administrativa personal identificable.')
    key, config = _definition(data['definition_digest'])
    band = next(band for band in config['sizes'] if band['id'] == data['size'])
    samples = [(pk, cost) for _, pk, cost in _samples(key, [band['id']])]
    summary, corpus = _coverage(key, band, samples, None)
    if data['corpus_digest'] != summary['corpus_digest']:
        raise CalculatorConflict('El corpus cambió. Consulta los cierres vigentes y vuelve a revisarlo.')
    if summary['covers_verified_median_cost'] is None:
        raise ValidationError('La revisión económica requiere costo respaldado y valor estándar comparables.')
    row, created = CalculatorCostReview.objects.get_or_create(
        definition_digest=key, size=band['id'], corpus_digest=summary['corpus_digest'],
        defaults={'note': data['note'], 'author': actor, 'corpus': {
            **corpus, 'median_verified_cost_cop': summary['median_verified_cost_cop'],
            'standard_value_cop': band['standard_value_cop']}},
    )
    if not created and (row.note != data['note'] or row.author_id != actor.pk):
        raise CalculatorConflict('Este corpus ya tiene una decisión documentada.')
    return _coverage(key, band, samples, row)[0]
