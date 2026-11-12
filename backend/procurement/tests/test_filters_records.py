"""Behavioral coverage for shared SECOP filters and personal follow-up records."""

import pytest
from procurement.filters import apply_filters, validate_filters
from procurement.models import Activity, SavedSearch
from procurement.services.records import classify, save_search
from rest_framework.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def test_combined_filters_return_only_the_matching_opportunity(opportunity):
    """Falla si entidad o presupuesto pasan como alternativas y llegan procesos ajenos."""
    keyword_match = opportunity('KEYWORD-ONLY', title='Asesoría especializada SECOP', unspsc_code='72100000', budget='5000000.00')
    unspsc_match = opportunity('UNSPSC-ONLY', title='Obra civil', unspsc_code='80101500', budget='5000000.00')
    opportunity('WRONG-ENTITY', title='Asesoría especializada SECOP', entity_name='Entidad ajena', budget='5000000.00')
    opportunity('WRONG-BUDGET', title='Asesoría especializada SECOP', budget='9000000.00')

    matches = apply_filters(
        type(keyword_match).objects.all(),
        {
            'entity_names': ['Entidad Nacional'],
            'min_budget': '4000000',
            'max_budget': '6000000',
            'keywords': ['especializada'],
            'unspsc_codes': ['801015'],
        },
    )

    assert set(matches.values_list('source_id', flat=True)) == {keyword_match.source_id, unspsc_match.source_id}


def test_filter_validation_rejects_inverted_budget_range():
    """Falla si un rango de presupuesto invertido permite alertar procesos fuera del límite."""
    with pytest.raises(ValidationError) as exc:
        validate_filters({'min_budget': '8000000', 'max_budget': '4000000'})

    assert exc.value.detail == {'max_budget': ['Debe ser mayor o igual al inicio del rango.']}


def test_discard_requires_a_reason(opportunity, staff_user):
    """Falla si se descarta una oportunidad sin explicar el motivo."""
    record = opportunity('CLASSIFY-1')

    with pytest.raises(ValidationError) as exc:
        classify(record.pk, {'state': 'discarded', 'notes': ''}, staff_user, staff_user)

    assert exc.value.detail == {'notes': ['Indica el motivo del descarte.']}


def test_restore_recovers_previous_state_and_writes_audit_activity(opportunity, staff_user):
    """Falla si restaurar un descarte no devuelve su estado anterior con evidencia."""
    record = opportunity('RESTORE-1')
    discarded = classify(record.pk, {'state': 'discarded', 'notes': 'No acredita experiencia requerida.'}, staff_user, staff_user)
    restored = classify(record.pk, {}, staff_user, staff_user, restore=True)

    assert discarded['state'] == 'discarded'
    assert restored['state'] == 'interesting'
    assert restored['notes'] == 'No acredita experiencia requerida.'
    assert Activity.objects.filter(classification_id=restored['id'], action='restore').exists()


def test_saved_searches_keep_one_favorite_per_owner(staff_user):
    """Falla si un administrador conserva más de una búsqueda favorita."""
    first = save_search({'name': 'Servicios', 'filters': {}, 'is_favorite': True}, staff_user)
    second = save_search({'name': 'Obras', 'filters': {}, 'is_favorite': True}, staff_user)

    assert list(SavedSearch.objects.filter(owner=staff_user, is_favorite=True).values_list('pk', flat=True)) == [second['id']]
    assert SavedSearch.objects.get(pk=first['id']).is_favorite is False


def test_saved_search_update_returns_not_found_for_another_owner(other_staff_user, staff_client):
    """Falla si un administrador puede actualizar una búsqueda privada ajena."""
    foreign = save_search({'name': 'Privada', 'filters': {}}, other_staff_user)

    response = staff_client.patch(f"/api/procurement/searches/{foreign['id']}/", {'name': 'Tomada'}, format='json')

    assert response.status_code == 404
    assert SavedSearch.objects.get(pk=foreign['id']).name == 'Privada'
