"""Durable scans must never hide findings after failure or accept new evidence."""
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from content.models import DataIntegrityFinding, DataIntegrityReview, DataIntegrityScan
from content.services.data_integrity import observations
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_documents_factories import make_document

pytestmark = pytest.mark.django_db


def complete(request_id='scan', scope=None, rules=None):
    scan = observations.start_scan(scope or resolve_scope('all'), request_id=request_id,
        filters={'rule_ids': rules or ['DC11']})
    observations.run_scan(scan.pk)
    scan.refresh_from_db()
    return scan


def test_repeat_scan_reuses_one_finding():
    make_document('Sin carpeta')
    complete()

    complete('again')

    assert DataIntegrityFinding.objects.count() == 1
    assert observations.list_findings()['count'] == 1


def test_failed_scan_keeps_previous_pending(monkeypatch):
    make_document('Sin carpeta')
    complete()
    monkeypatch.setattr(observations.engine, 'detect', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('private')))

    failed = complete('failed')

    assert failed.status == 'failed'
    assert failed.error_code == 'scan_failed'
    assert observations.list_findings()['count'] == 1


def test_acceptance_survives_same_evidence(superuser):
    make_document('Sin carpeta')
    complete()
    finding = DataIntegrityFinding.objects.get()
    observations.review_finding(finding.fingerprint, action='accept', reason='Organización intencional',
        request_id='review', actor=superuser, source='panel')

    complete('again')

    assert observations.list_findings()['count'] == 0
    assert observations.list_findings(status='accepted')['count'] == 1
    assert DataIntegrityReview.objects.get().reason == 'Organización intencional'


def test_changed_evidence_returns_to_pending(superuser):
    """An acceptance must not hide a different folder association."""
    from content.tests.data_integrity_documents_factories import make_folder
    first, second = make_folder('Primera'), make_folder('Segunda')
    document = make_document('Acta', folder=first)
    # DC9 includes the chosen folder in its evidence; changing it must not
    # inherit an earlier acceptance for another location.
    from django.contrib.auth import get_user_model
    owner = get_user_model().objects.create_user(username='owner')
    other = get_user_model().objects.create_user(username='other')
    first.client_user = other; first.save()
    second.client_user = other; second.save()
    type(document).objects.filter(pk=document.pk).update(client_user=owner)
    complete(rules=['DC9'])
    finding = DataIntegrityFinding.objects.get()
    observations.review_finding(finding.fingerprint, action='accept', reason='Intencional',
        request_id='review', actor=superuser, source='panel')
    type(document).objects.filter(pk=document.pk).update(folder=second)

    complete('changed', rules=['DC9'])

    assert observations.list_findings()['count'] == 1


def test_scoped_scan_does_not_resolve_unrelated_finding():
    first, second = make_document('Uno'), make_document('Dos')
    complete()

    complete('scoped', scope=resolve_scope('document', first.pk))

    assert observations.list_findings()['count'] == 2


def test_completed_sweep_resolves_absent_finding():
    from content.tests.data_integrity_documents_factories import make_folder
    document = make_document('Acta')
    complete()
    type(document).objects.filter(pk=document.pk).update(folder=make_folder('Destino'))

    complete('fixed')

    assert observations.list_findings()['count'] == 0
    assert observations.list_findings(status='resolved')['count'] == 1


@freeze_time('2026-11-05 08:00:00+00:00')
def test_recovered_worker_cannot_publish_old_results():
    from content.models import DataIntegrityScanLease
    first = observations.start_scan(resolve_scope('all'), request_id='old')
    claimed = observations._claim(first.pk)
    DataIntegrityScanLease.objects.filter(key='scan').update(expires_at=timezone.now() - timedelta(seconds=1))
    second = observations.start_scan(resolve_scope('all'), request_id='new')
    observations._claim(second.pk)

    published = observations._publish(claimed, resolve_scope('all'), [], {'evaluated_rules': ['DC11']})

    assert published is False
    first.refresh_from_db()
    assert first.status == 'failed'


def test_reopening_returns_accepted_finding_to_pending(superuser):
    make_document('Acta')
    complete()
    finding = DataIntegrityFinding.objects.get()
    observations.review_finding(finding.fingerprint, action='accept', reason='Intencional',
        request_id='accept', actor=superuser, source='panel')

    observations.review_finding(finding.fingerprint, action='reopen', reason='Revisar de nuevo',
        request_id='reopen', actor=superuser, source='panel')

    assert observations.list_findings()['count'] == 1


def test_result_limit_does_not_publish_partial_findings(settings):
    make_document('Uno')
    make_document('Dos')
    settings.DATA_INTEGRITY_MAX_FINDINGS = 1

    limited = complete('limited')

    assert limited.status == 'failed'
    assert limited.error_code == 'scan_result_limit'
    assert DataIntegrityFinding.objects.count() == 0
