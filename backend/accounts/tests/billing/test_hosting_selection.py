"""Hosting selection choices exposed while preparing a collection account."""
from datetime import date

import pytest
from django.contrib.auth import get_user_model

from accounts.models import (
    BillingContextEvent,
    HostingEvidence,
    ProjectHosting,
    ProjectHostingAccountingSource,
)
from accounts.services.billing_context import associate_account
from accounts.services.hosting_context import reconcile_evidence, reconcile_hosting
from accounts.services.hosting_selection import hosting_selection
from content.models import HostingCycle, HostingRecord
from content.services.collection_account_snapshot_service import persist_collection_account_pdf


User = get_user_model()
pytestmark = pytest.mark.django_db


def selection_inventory(*, hosting=None, sources=None, subscriptions=None, version=0):
    return {
        'hosting': hosting,
        'accounting_sources': sources or [],
        'subscriptions': subscriptions or [],
        'version': version,
    }


def source(*, record_id=101, mapped_hosting_id=None, conflicts=None,
           domain_url='cliente.example', payment_modality='quarterly', is_active=True):
    return {
        'id': record_id,
        'mapped_hosting_id': mapped_hosting_id,
        'conflicts': conflicts or [],
        'domain_url': domain_url,
        'payment_modality': payment_modality,
        'is_active': is_active,
    }


def hosting_mapping(record, *, expected_version=0, subscription_id=None,
                    operational_record_id=None):
    return {
        'expected_version': expected_version,
        'reason': 'Se confirma la identidad del hosting según sus referencias.',
        'subscription_id': subscription_id,
        'hosting_record_ids': [record.pk],
        'operational_record_id': operational_record_id or record.pk,
    }


def test_associated_record_exposes_recognition_details():
    """Falla si un hosting ya asociado deja de mostrar datos para reconocerlo."""
    result = hosting_selection(selection_inventory(
        hosting={'id': 7, 'operational_record_id': 101, 'subscription_id': None},
        sources=[source(mapped_hosting_id=7, domain_url='sitio.example', payment_modality='semiannual')],
        version=4,
    ))

    assert result == {
        'candidates': [{
            'hosting_record_id': 101,
            'project_hosting_id': 7,
            'domain_url': 'sitio.example',
            'payment_modality': 'semiannual',
            'is_active': True,
            'requires_association': False,
            'selectable': True,
            'historical': False,
        }],
        'blockers': [],
        'can_create': False,
        'requires_reconciliation': False,
        'version': 4,
    }


def test_unique_unmapped_record_is_selectable_with_explicit_association():
    """Falla si el único registro válido se oculta en vez de pedir asociación explícita."""
    result = hosting_selection(selection_inventory(sources=[source()]))

    assert result['candidates'][0]['hosting_record_id'] == 101
    assert result['candidates'][0]['requires_association'] is True
    assert result['candidates'][0]['selectable'] is True
    assert result['requires_reconciliation'] is False


def test_empty_inventory_allows_hosting_creation():
    """Falla si la ausencia de hosting no ofrece crear uno dentro del flujo."""
    result = hosting_selection(selection_inventory())

    assert result['candidates'] == []
    assert result['blockers'] == []
    assert result['can_create'] is True
    assert result['requires_reconciliation'] is False


def test_empty_hosting_container_is_not_a_billable_candidate():
    """Falla si un contenedor administrativo vacío se ofrece como hosting seleccionable."""
    result = hosting_selection(selection_inventory(
        hosting={'id': 7, 'operational_record_id': None, 'subscription_id': None},
    ))

    assert result['candidates'] == []
    assert result['can_create'] is True


def test_conflicting_source_requires_reconciliation():
    """Falla si una referencia contradictoria se puede seleccionar para cobrar."""
    result = hosting_selection(selection_inventory(
        sources=[source(conflicts=['Cliente distinto o pendiente.'])],
    ))

    assert result['candidates'][0]['selectable'] is False
    assert result['requires_reconciliation'] is True
    assert result['blockers'] == [{
        'code': 'source_conflict',
        'record_id': 101,
        'message': ('Hosting #101: Cliente distinto o pendiente. '
                    'Corrige sus referencias antes de vincularlo.'),
    }]


def test_record_mapped_to_another_hosting_requires_reconciliation():
    """Falla si un registro de otro hosting se vuelve elegible para este proyecto."""
    result = hosting_selection(selection_inventory(
        hosting={'id': 7, 'operational_record_id': 101, 'subscription_id': None},
        sources=[source(mapped_hosting_id=9)],
    ))

    assert result['candidates'][0]['selectable'] is False
    assert result['requires_reconciliation'] is True
    assert result['blockers'][0]['code'] == 'source_conflict'
    assert 'otro proyecto' in result['blockers'][0]['message']


@pytest.mark.parametrize(
    ('inventory', 'blocker_index', 'blocker_code'),
    [
        (selection_inventory(sources=[source(record_id=101), source(record_id=102)]), 0, 'multiple_pending_sources'),
        (selection_inventory(
            hosting={'id': 7, 'operational_record_id': 101, 'subscription_id': None},
            sources=[source(record_id=101, mapped_hosting_id=7)],
            subscriptions=[{'id': 55, 'plan': 'quarterly', 'status': 'active'}],
        ), 0, 'subscription_pending'),
        (selection_inventory(
            hosting={'id': 7, 'operational_record_id': 101, 'subscription_id': None},
            sources=[source(record_id=101, mapped_hosting_id=7), source(record_id=102)],
        ), 0, 'operational_change'),
        (selection_inventory(sources=[source(record_id=101), source(record_id=102)]), 1, 'operational_missing'),
    ],
)
def test_ambiguous_hosting_sources_require_reconciliation(inventory, blocker_index, blocker_code):
    """Falla si una selección ambigua omite la conciliación administrativa."""
    result = hosting_selection(inventory)

    assert result['requires_reconciliation'] is True
    assert result['blockers'][blocker_index]['code'] == blocker_code
    assert result['candidates'][0]['selectable'] is False


def test_subscription_only_association_is_a_selectable_hosting_identity():
    """Falla si una suscripción asociada sin registro contable desaparece del selector."""
    result = hosting_selection(selection_inventory(
        hosting={'id': 7, 'operational_record_id': None, 'subscription_id': 55},
        subscriptions=[{'id': 55, 'plan': 'annual', 'status': 'active'}],
    ))

    assert result['candidates'] == [{
        'hosting_record_id': None,
        'project_hosting_id': 7,
        'domain_url': '',
        'payment_modality': 'annual',
        'is_active': True,
        'requires_association': False,
        'selectable': True,
        'historical': False,
    }]
    assert result['can_create'] is False


def test_panel_hosting_selection_returns_existing_identity_without_mutation(
    api_client, project, admin_user, hosting_record,
):
    """Falla si el GET del panel altera el hosting al cargar una opción existente."""
    superuser = User.objects.create_superuser(
        username='selection-superuser', email='selection-superuser@example.test', password='test-password',
    )
    hosting_record.domain_url = 'panel.example'
    hosting_record.payment_modality = HostingRecord.Modality.SEMIANNUAL
    hosting_record.save(update_fields=['domain_url', 'payment_modality'])
    identity = reconcile_hosting(project.pk, superuser, hosting_mapping(hosting_record))
    before = (ProjectHosting.objects.count(), BillingContextEvent.objects.count(), identity['version'])
    api_client.force_login(superuser)

    response = api_client.get(f'/api/admin/billing-context/projects/{project.pk}/hosting/')

    assert response.status_code == 200, response.data
    assert response.data['selection']['candidates'] == [{
        'hosting_record_id': hosting_record.pk,
        'project_hosting_id': identity['id'],
        'domain_url': 'panel.example',
        'payment_modality': 'semiannual',
        'is_active': True,
        'requires_association': False,
        'selectable': True,
        'historical': False,
    }]
    assert (ProjectHosting.objects.count(), BillingContextEvent.objects.count(),
            ProjectHosting.objects.get(pk=identity['id']).version) == before


def test_panel_hosting_selection_rejects_non_superuser(api_client, project, admin_user):
    """Falla si una cuenta administrativa sin superusuario consulta el selector de hosting."""
    api_client.force_login(admin_user)

    response = api_client.get(f'/api/admin/billing-context/projects/{project.pk}/hosting/')

    assert response.status_code == 403
    assert ProjectHosting.objects.filter(project=project).count() == 0
    assert BillingContextEvent.objects.filter(project=project).count() == 0


def reconciled_account_snapshot(project, admin_user, hosting_record, subscription, payment, account):
    """Arrange an issued account with explicit hosting evidence before a new source is linked."""
    identity = reconcile_hosting(
        project.pk,
        admin_user,
        hosting_mapping(hosting_record, subscription_id=subscription.pk),
    )
    associate_account(account.pk, admin_user, {
        'billing_nature': 'hosting',
        'project_hosting_id': identity['id'],
        'hosting_payment_id': payment.pk,
        'expected_version': 0,
        'reason': 'La cuenta conserva la obligación de hosting seleccionada.',
    })
    cycle = HostingCycle.objects.create(
        hosting_record=hosting_record,
        modality='quarterly',
        amount=payment.amount,
        paid_at=date(2026, 1, 1),
    )
    reconcile_evidence(project.pk, admin_user, {
        'expected_version': 2,
        'reason': 'El ciclo histórico pertenece al mismo servicio.',
        'label': 'Ciclo inicial',
        'cycle_ids': [cycle.pk],
    })
    stored_pdf = persist_collection_account_pdf(
        account,
        pdf_bytes=b'%PDF-1.4 historical hosting account',
    )
    additional_record = HostingRecord.objects.create(
        project=project,
        client=project.client.profile,
        client_name='Titular adicional',
        monthly_value=50000,
        payment_per_cycle=150000,
    )
    return identity, cycle, additional_record, stored_pdf.pdf_bytes


def test_reconciliation_preserves_existing_account_financial_snapshot(
    project, admin_user, hosting_record, subscription, payment, account,
):
    """Falla si vincular otra fuente modifica el snapshot financiero de la cuenta existente."""
    identity, cycle, additional_record, stored_pdf = reconciled_account_snapshot(
        project,
        admin_user,
        hosting_record,
        subscription,
        payment,
        account,
    )
    original = (account.commercial_status, account.total, payment.status, payment.amount,
                cycle.amount, stored_pdf)

    result = reconcile_hosting(project.pk, admin_user, {
        **hosting_mapping(
            additional_record,
            expected_version=3,
            subscription_id=subscription.pk,
            operational_record_id=hosting_record.pk,
        ),
    })

    account.refresh_from_db()
    payment.refresh_from_db()
    cycle.refresh_from_db()
    event = BillingContextEvent.objects.filter(project=project).latest('id')
    assert result['hosting_record_ids'] == [hosting_record.pk, additional_record.pk]
    assert result['operational_record_id'] == hosting_record.pk
    assert (account.commercial_status, account.total, payment.status, payment.amount,
            cycle.amount, account.generated_file.read()) == original
    assert HostingEvidence.objects.get(document=account).group.evidence.filter(payment=payment).count() == 1
    assert ProjectHostingAccountingSource.objects.filter(
        hosting_id=identity['id'], hosting_record=additional_record,
    ).count() == 1
    assert event.operation == 'reconcile_hosting_identity'
    assert event.before['operational_record_id'] == hosting_record.pk
    assert event.after['hosting_record_ids'] == [hosting_record.pk, additional_record.pk]
