from datetime import date
import pytest
from rest_framework.exceptions import ValidationError
from accounts.models import CollectionAccountContext, HostingEvidence, Payment, ProjectHosting
from accounts.services.billing_access import BillingConflict
from accounts.services.billing_context import associate_account, validate_account_context
from accounts.services.hosting_context import hosting_inventory, reconcile_evidence, reconcile_hosting
from content.models import Document, HostingCycle, HostingRecord

pytestmark = pytest.mark.django_db


def mapping(record, subscription=None, **kwargs):
    return {'expected_version': 0, 'reason': 'Se confirma el servicio por sus referencias originales',
            'hosting_record_ids': [record.pk], 'operational_record_id': record.pk,
            'subscription_id': subscription.pk if subscription else None, **kwargs}


def test_identity_mapping_preserves_original_sources(project, admin_user, hosting_record, payment):
    before = (Payment.objects.count(), HostingRecord.objects.count(), HostingCycle.objects.count())
    result = reconcile_hosting(project.pk, admin_user, mapping(hosting_record, payment.subscription))
    assert result['subscription_id'] == payment.subscription_id
    assert result['operational_record_id'] == hosting_record.pk
    assert (Payment.objects.count(), HostingRecord.objects.count(), HostingCycle.objects.count()) == before


def test_preview_creates_no_identity(project, admin_user, hosting_record):
    result = reconcile_hosting(project.pk, admin_user, mapping(hosting_record), preview=True)
    assert result['proposal']['financial_effect'] == 'none'
    assert not ProjectHosting.objects.filter(project=project).exists()


def test_multiple_historical_origins_require_explicit_choice(project, admin_user, hosting_record):
    other = HostingRecord.objects.create(project=project, client=project.client.profile, client_name='Anterior', monthly_value=10000)
    inventory = hosting_inventory(project.pk, admin_user)
    assert len(inventory['accounting_sources']) == 2
    assert inventory['hosting'] is None
    result = reconcile_hosting(project.pk, admin_user, mapping(hosting_record, hosting_record_ids=[hosting_record.pk, other.pk], operational_record_id=other.pk))
    assert result['operational_record_id'] == other.pk
    assert HostingRecord.objects.filter(project=project).count() == 2


def test_foreign_client_origin_is_rejected(project, admin_user, hosting_record):
    hosting_record.client = admin_user.profile
    hosting_record.save()
    with pytest.raises(ValidationError, match='cliente/proyecto'):
        reconcile_hosting(project.pk, admin_user, mapping(hosting_record))
    assert not ProjectHosting.objects.filter(project=project).exists()


def test_foreign_subscription_is_rejected(project, admin_user, hosting_record, subscription):
    from accounts.models import Project
    other = Project.objects.create(name='Otro', client=project.client)
    subscription.project = other
    subscription.save()
    with pytest.raises(ValidationError, match='suscripción'):
        reconcile_hosting(project.pk, admin_user, mapping(hosting_record, subscription))


def test_stale_reconciliation_does_not_change_identity(project, admin_user, hosting_record):
    reconcile_hosting(project.pk, admin_user, mapping(hosting_record))
    with pytest.raises(BillingConflict):
        reconcile_hosting(project.pk, admin_user, mapping(hosting_record))
    assert ProjectHosting.objects.get(project=project).version == 1


def test_same_obligation_has_one_explicit_evidence_group(project, admin_user, hosting_record, payment, account):
    identity = reconcile_hosting(project.pk, admin_user, mapping(hosting_record, payment.subscription))
    cycle = HostingCycle.objects.create(hosting_record=hosting_record, modality='quarterly', amount=payment.amount, paid_at=date(2026, 1, 1))
    associate_account(account.pk, admin_user, {'billing_nature': 'hosting', 'project_hosting_id': identity['id'], 'expected_version': 0, 'reason': 'Cobro del servicio'})
    result = reconcile_evidence(project.pk, admin_user, {'expected_version': 1, 'reason': 'Equivalencia confirmada por documentos', 'label': 'Ciclo 1',
                                                       'payment_ids': [payment.pk], 'cycle_ids': [cycle.pk], 'document_ids': [account.pk]})
    assert {(row['payment_id'], row['cycle_id'], row['document_id']) for row in result['evidence']} == {
        (payment.pk, None, None), (None, cycle.pk, None), (None, None, account.pk),
    }
    assert set(HostingEvidence.objects.filter(group_id=result['id']).values_list('group_id', flat=True)) == {result['id']}
    assert Payment.objects.count() == 1
    assert HostingCycle.objects.count() == 1
    assert Document.objects.filter(pk=account.pk).get().commercial_status == 'issued'


def test_evidence_cannot_belong_to_two_groups(project, admin_user, hosting_record, payment):
    reconcile_hosting(project.pk, admin_user, mapping(hosting_record, payment.subscription))
    data = {'expected_version': 1, 'reason': 'Confirmado', 'label': 'Obligación', 'payment_ids': [payment.pk]}
    reconcile_evidence(project.pk, admin_user, data)
    with pytest.raises(ValidationError, match='ya está conciliada'):
        reconcile_evidence(project.pk, admin_user, {**data, 'expected_version': 2})
    assert HostingEvidence.objects.filter(payment=payment).count() == 1


def test_evidence_correction_retains_prior_membership_audit(project, admin_user, hosting_record, payment):
    reconcile_hosting(project.pk, admin_user, mapping(hosting_record, payment.subscription))
    group = reconcile_evidence(project.pk, admin_user, {'expected_version': 1, 'reason': 'Confirmado', 'label': 'Obligación', 'payment_ids': [payment.pk]})
    reconcile_evidence(project.pk, admin_user, {'expected_version': 2, 'reason': 'Equivalencia revocada tras revisión', 'label': 'Revisión', 'group_id': group['id'], 'payment_ids': []})
    assert not HostingEvidence.objects.filter(payment=payment).exists()
    event = project.billing_context_events.latest('id')
    assert event.before['evidence'][0]['payment_id'] == payment.pk
    assert Payment.objects.filter(pk=payment.pk).exists()


def test_subscription_account_requires_explicit_obligation_link(project, admin_user, hosting_record, payment, account):
    identity = reconcile_hosting(project.pk, admin_user, mapping(hosting_record, payment.subscription))
    associate_account(account.pk, admin_user, {'billing_nature': 'hosting', 'project_hosting_id': identity['id'], 'expected_version': 0, 'reason': 'Contexto confirmado'})
    with pytest.raises(ValidationError, match='obligación de la suscripción'):
        validate_account_context(account)


def test_subscription_account_can_link_existing_obligation(project, admin_user, hosting_record, payment, account):
    identity = reconcile_hosting(project.pk, admin_user, mapping(hosting_record, payment.subscription))
    associate_account(account.pk, admin_user, {'billing_nature': 'hosting', 'project_hosting_id': identity['id'], 'hosting_payment_id': payment.pk, 'expected_version': 0, 'reason': 'Obligación seleccionada explícitamente'})
    validate_account_context(account)
    assert account.hosting_evidence.group.evidence.filter(payment=payment).exists()


def test_historical_source_cannot_emit_in_place_of_operational_source(project, admin_user, hosting_record, account):
    other = HostingRecord.objects.create(project=project, client=project.client.profile, client_name='Anterior', monthly_value=10000)
    identity = reconcile_hosting(project.pk, admin_user, mapping(hosting_record, hosting_record_ids=[hosting_record.pk, other.pk]))
    account.hosting_record = other
    account.save()
    associate_account(account.pk, admin_user, {'billing_nature': 'hosting', 'project_hosting_id': identity['id'], 'expected_version': 0, 'reason': 'Historia confirmada'})
    with pytest.raises(ValidationError, match='operativo'):
        validate_account_context(account)
