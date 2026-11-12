"""Private panel contracts for durable integrity scans and human reviews."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from content.models import DataIntegrityFinding, DataIntegrityReview, DataIntegrityScan

pytestmark = pytest.mark.django_db

SCANS = reverse('data-integrity-scans')
REVIEWS = reverse('data-integrity-reviews')
REVIEW = reverse('data-integrity-review')


def _finding(*, is_present=True):
    scan = DataIntegrityScan.objects.create(
        request_id='stored-scan', scope={'kind': 'all', 'id': None}, filters={},
        source='panel', catalog_version='1.2.0', status='completed',
    )
    return DataIntegrityFinding.objects.create(
        fingerprint='a' * 64, rule_id='DC11', domain='documents', severity='medium',
        payload={'title': 'Documento sin carpeta'}, is_present=is_present,
        last_seen_at=timezone.now(), last_scan=scan,
    )


@pytest.mark.parametrize(
    ('method', 'url'),
    [
        ('get', SCANS), ('post', SCANS), ('get', REVIEWS), ('post', REVIEW),
        ('get', reverse('data-integrity-scan', args=[1])),
    ],
)
def test_non_staff_user_is_refused_from_observation_routes(method, url):
    """Fails if a non-administrator can inspect or alter durable integrity evidence."""
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user(username='member', password='secret'))

    response = getattr(client, method)(url, {}, format='json')

    assert response.status_code == 403


def test_review_replay_keeps_one_audit_entry(admin_client):
    """Fails if a retried acceptance creates two audit decisions for the same request."""
    finding = _finding()
    payload = {
        'fingerprint': finding.fingerprint, 'action': 'accept',
        'reason': 'Caso intencional', 'request_id': 'accept-once',
    }

    first = admin_client.post(REVIEW, payload, format='json')
    replay = admin_client.post(REVIEW, payload, format='json')

    finding.refresh_from_db()
    assert first.status_code == 200
    assert replay.data['review_id'] == first.data['review_id']
    assert (finding.is_accepted, DataIntegrityReview.objects.count()) == (True, 1)


def test_review_request_id_rejects_changed_decision(admin_client):
    """Fails if one review request id can accept a finding and later reopen it."""
    finding = _finding()
    accepted = admin_client.post(REVIEW, {
        'fingerprint': finding.fingerprint, 'action': 'accept',
        'reason': 'Caso intencional', 'request_id': 'one-decision',
    }, format='json')

    conflict = admin_client.post(REVIEW, {
        'fingerprint': finding.fingerprint, 'action': 'reopen',
        'reason': 'Cambió la evidencia', 'request_id': 'one-decision',
    }, format='json')

    assert accepted.status_code == 200
    assert (conflict.status_code, conflict.data['code']) == (409, 'request_conflict')


def test_review_rejects_a_resolved_finding(admin_client):
    """Fails if an already resolved finding can be accepted as current evidence."""
    finding = _finding(is_present=False)

    response = admin_client.post(REVIEW, {
        'fingerprint': finding.fingerprint, 'action': 'accept',
        'reason': 'Caso intencional', 'request_id': 'resolved-finding',
    }, format='json')

    assert (response.status_code, response.data['code']) == (409, 'finding_resolved')
