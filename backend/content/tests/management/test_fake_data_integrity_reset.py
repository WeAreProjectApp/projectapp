"""Development reset clears observed integrity history without losing its mutex."""
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from content.models import (
    DataIntegrityFinding,
    DataIntegrityReview,
    DataIntegrityScan,
    DataIntegrityScanLease,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def observed_integrity():
    actor = get_user_model().objects.create_user(
        username='previous-integrity-operator', is_staff=True,
    )
    scan = DataIntegrityScan.objects.create(
        request_id='observed-scan', actor=actor, source='panel',
        catalog_version='1.2.0', scope={'kind': 'all', 'id': None}, status='completed',
    )
    finding = DataIntegrityFinding.objects.create(
        fingerprint='a' * 64, rule_id='DC11', domain='documents',
        severity='low', last_scan=scan, last_seen_at=timezone.now(),
        is_accepted=True,
    )
    DataIntegrityReview.objects.create(
        finding=finding, actor=actor, source='panel', action='accept',
        reason='Ubicación revisada', request_id='observed-review',
        payload_hash='b' * 64,
    )
    running_scan = DataIntegrityScan.objects.create(
        request_id='interrupted-scan', actor=actor, source='panel',
        catalog_version='1.2.0', scope={'kind': 'all', 'id': None}, status='running',
    )
    DataIntegrityScanLease.objects.update_or_create(
        key='scan', defaults={'scan': running_scan, 'expires_at': timezone.now()},
    )
    actor.is_staff = False
    actor.save(update_fields=['is_staff'])
    return actor.pk


def test_development_reset_clears_integrity_history(observed_integrity):
    call_command('delete_fake_data', '--confirm', stdout=StringIO(), verbosity=0)

    assert (
        DataIntegrityReview.objects.count(),
        DataIntegrityFinding.objects.count(),
        DataIntegrityScan.objects.count(),
    ) == (0, 0, 0)
    assert not get_user_model().objects.filter(pk=observed_integrity).exists()
    assert list(DataIntegrityScanLease.objects.values_list(
        'key', 'scan_id', 'expires_at',
    )) == [('scan', None, None)]


def test_development_reset_requires_explicit_capability(observed_integrity, settings):
    settings.FAKE_DATA_ALLOWED = False

    with pytest.raises(CommandError, match='FAKE_DATA_ALLOWED=True'):
        call_command('delete_fake_data', '--confirm', stdout=StringIO(), verbosity=0)

    assert DataIntegrityReview.objects.count() == 1
    assert DataIntegrityScanLease.objects.get(key='scan').scan_id is not None


def test_development_reset_requires_confirmation(observed_integrity):
    call_command('delete_fake_data', stdout=StringIO(), verbosity=0)

    assert DataIntegrityReview.objects.count() == 1
    assert DataIntegrityScanLease.objects.get(key='scan').scan_id is not None
