"""Public proposal module-interest endpoint behavior."""
from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal

import pytest
from django.urls import reverse

from content.models import (
    AdditionalModule,
    AdditionalModuleCategory,
    ProposalChangeLog,
)

pytestmark = pytest.mark.django_db


def _interest_url(proposal):
    return reverse('proposal-module-interests', kwargs={'proposal_uuid': proposal.uuid})


def _module(category, slug, order):
    return AdditionalModule.objects.create(
        category=category,
        slug=slug,
        order=order,
        name_es=f'Módulo {slug}',
        name_en=f'{slug} module',
        summary_es='Resume una capacidad comercial.',
        summary_en='Summarizes a commercial capability.',
        what_is_es='Una capacidad adicional.',
        what_is_en='An additional capability.',
        purpose_es='Resolver una necesidad concreta.',
        purpose_en='Solve one concrete need.',
        problems_solved_es=['Evita trabajo manual.'],
        problems_solved_en=['Avoids manual work.'],
        integrations_es=['Flujo principal.'],
        integrations_en=['Core flow.'],
        implementation_requirements_es=['Definir reglas.'],
        implementation_requirements_en=['Define rules.'],
    )


@pytest.fixture
def catalog_modules():
    category = AdditionalModuleCategory.objects.create(
        slug='commercial-growth',
        name_es='Crecimiento comercial',
        name_en='Commercial growth',
        order=999,
    )
    return (
        _module(category, 'crm', 900),
        _module(category, 'automation', 901),
    )


def test_put_persists_catalog_snapshot_without_changing_contracted_scope(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si expresar interés cambia la inversión o el alcance contratado."""
    crm, automation = catalog_modules
    sent_proposal.total_investment = Decimal('25000.00')
    sent_proposal.selected_modules = ['module-existing-scope']
    sent_proposal.save(update_fields=['total_investment', 'selected_modules'])

    response = api_client.put(
        _interest_url(sent_proposal),
        {'module_ids': [automation.id, crm.id]},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 200
    assert [item['id'] for item in response.data['modules']] == [crm.id, automation.id]
    assert sent_proposal.total_investment == Decimal('25000.00')
    assert sent_proposal.selected_modules == ['module-existing-scope']
    assert sent_proposal.module_interests == [
        {
            'id': crm.id,
            'slug': 'crm',
            'name_es': 'Módulo crm',
            'name_en': 'crm module',
            'category_es': 'Crecimiento comercial',
            'category_en': 'Commercial growth',
        },
        {
            'id': automation.id,
            'slug': 'automation',
            'name_es': 'Módulo automation',
            'name_en': 'automation module',
            'category_es': 'Crecimiento comercial',
            'category_en': 'Commercial growth',
        },
    ]
    assert sent_proposal.module_interests_updated_at is not None
    assert ProposalChangeLog.objects.filter(
        proposal=sent_proposal,
        change_type=ProposalChangeLog.ChangeType.MODULE_INTERESTS,
        actor_type=ProposalChangeLog.ActorType.CLIENT,
    ).count() == 1


def test_put_rejects_duplicate_module_ids_without_replacing_interests(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si una lista duplicada borra o reemplaza intereses ya guardados."""
    crm, _automation = catalog_modules
    sent_proposal.module_interests = [{'id': crm.id, 'slug': crm.slug}]
    sent_proposal.save(update_fields=['module_interests'])

    response = api_client.put(
        _interest_url(sent_proposal),
        {'module_ids': [crm.id, crm.id]},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 400
    assert response.data['module_ids'] == ['No repitas módulos en la selección.']
    assert sent_proposal.module_interests == [{'id': crm.id, 'slug': crm.slug}]


def test_put_rejects_unavailable_module_without_replacing_interests(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si un módulo retirado sobrescribe los intereses existentes."""
    crm, automation = catalog_modules
    sent_proposal.module_interests = [{'id': crm.id, 'slug': crm.slug}]
    sent_proposal.save(update_fields=['module_interests'])
    automation.is_active = False
    automation.save(update_fields=['is_active'])

    response = api_client.put(
        _interest_url(sent_proposal),
        {'module_ids': [automation.id]},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 400
    assert response.data['module_ids'] == 'Hay módulos que ya no están disponibles.'
    assert sent_proposal.module_interests == [{'id': crm.id, 'slug': crm.slug}]


def test_put_removes_retired_interest_when_client_submits_empty_list(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si un interés histórico no puede retirarse después de desactivar su módulo."""
    crm, _automation = catalog_modules
    sent_proposal.module_interests = [{'id': crm.id, 'slug': crm.slug}]
    sent_proposal.save(update_fields=['module_interests'])
    crm.is_active = False
    crm.save(update_fields=['is_active'])

    response = api_client.put(
        _interest_url(sent_proposal),
        {'module_ids': []},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 200
    assert response.data['modules'] == []
    assert sent_proposal.module_interests == []


def test_put_with_identical_ids_does_not_advance_interest_activity(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si repetir la misma selección crea una señal comercial duplicada."""
    crm, _automation = catalog_modules
    original_timestamp = datetime(2026, 9, 29, 18, tzinfo=datetime_timezone.utc)
    sent_proposal.module_interests = [{'id': crm.id, 'slug': crm.slug}]
    sent_proposal.module_interests_updated_at = original_timestamp
    sent_proposal.save(update_fields=['module_interests', 'module_interests_updated_at'])

    response = api_client.put(
        _interest_url(sent_proposal),
        {'module_ids': [crm.id]},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 200
    assert sent_proposal.module_interests_updated_at == original_timestamp
    assert not ProposalChangeLog.objects.filter(proposal=sent_proposal).exists()


def test_put_retains_deactivated_interest_while_adding_active_module(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si ampliar intereses borra un módulo retirado que el cliente ya eligió."""
    crm, automation = catalog_modules
    previous_interest = {
        'id': crm.id,
        'slug': crm.slug,
        'name_es': 'Nombre histórico',
        'name_en': 'Historic name',
        'category_es': 'Categoría histórica',
        'category_en': 'Historic category',
    }
    sent_proposal.module_interests = [previous_interest]
    sent_proposal.save(update_fields=['module_interests'])
    crm.is_active = False
    crm.save(update_fields=['is_active'])

    response = api_client.put(
        _interest_url(sent_proposal),
        {'module_ids': [crm.id, automation.id]},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 200
    assert sent_proposal.module_interests[0] == previous_interest
    assert sent_proposal.module_interests[1]['id'] == automation.id
    assert [interest['id'] for interest in response.data['modules']] == [crm.id, automation.id]


def test_put_rejects_expired_proposal_without_writing_interest(
    api_client,
    expired_proposal,
    catalog_modules,
):
    """Falla si una propuesta expirada crea una señal comercial del cliente."""
    crm, _automation = catalog_modules

    response = api_client.put(
        _interest_url(expired_proposal),
        {'module_ids': [crm.id]},
        format='json',
    )

    expired_proposal.refresh_from_db()
    assert response.status_code == 410
    assert response.data == {'error': 'Esta propuesta ha expirado.'}
    assert expired_proposal.module_interests == []
    assert expired_proposal.module_interests_updated_at is None
    assert not ProposalChangeLog.objects.filter(proposal=expired_proposal).exists()


def test_preview_put_keeps_interest_timestamp_and_change_log_unchanged(
    api_client,
    sent_proposal,
    catalog_modules,
):
    """Falla si la previsualización persiste interés o agrega actividad comercial."""
    crm, _automation = catalog_modules

    response = api_client.put(
        f'{_interest_url(sent_proposal)}?preview=1',
        {'module_ids': [crm.id]},
        format='json',
    )

    sent_proposal.refresh_from_db()
    assert response.status_code == 200
    assert response.data == {'modules': [], 'updated_at': None, 'status': 'skipped'}
    assert sent_proposal.module_interests_updated_at is None
    assert not ProposalChangeLog.objects.filter(proposal=sent_proposal).exists()
