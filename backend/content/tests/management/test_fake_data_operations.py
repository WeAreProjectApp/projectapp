"""Replay, environment boundaries and rollback of the integrated seeders."""
from datetime import date
from io import BytesIO, StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F, Q
from django.utils import timezone
from freezegun import freeze_time
from pypdf import PdfReader

from accounts.models import Deliverable, Project
from content.fake_data_files import fake_data_transaction, sample_pdf
from content.models import Contact
from monitoring.models import Case, Resource
from secure_links import services
from secure_links.models import SecureLink, SecureLinkFolder

pytestmark = pytest.mark.django_db
SEED_ARGS = ('--seed', '231', '--anchor-date', '2026-11-06')


def run(name, *args):
    call_command(name, *args, *SEED_ARGS, stdout=StringIO(), verbosity=0)


@pytest.mark.parametrize('command', [
    'create_fake_monitoring', 'create_fake_secure_links', 'create_fake_platform_cases',
])
def test_module_command_rejects_production_even_with_capability(settings, command):
    settings.FAKE_DATA_ALLOWED = True
    settings.IS_PRODUCTION = True
    with pytest.raises(CommandError, match='disabled'):
        run(command)
    assert (Case.objects.count(), SecureLink.objects.count(), Project.objects.count()) == (0, 0, 0)


def test_monitoring_replays_business_values():
    run('create_fake_monitoring', '--count', '6')
    before = list(Case.objects.order_by('source__resource__key', 'fingerprint').values_list(
        'source__resource__key', 'fingerprint_hash', 'state', 'severity', 'first_seen_at', 'last_seen_at', 'evidence',
    ))
    call_command('delete_fake_data', '--confirm', stdout=StringIO())
    run('create_fake_monitoring', '--count', '6')
    assert list(Case.objects.order_by('source__resource__key', 'fingerprint').values_list(
        'source__resource__key', 'fingerprint_hash', 'state', 'severity', 'first_seen_at', 'last_seen_at', 'evidence',
    )) == before


def test_monitoring_resolved_cases_have_recovered_conditions():
    run('create_fake_monitoring', '--count', '6')
    assert not Case.objects.filter(state='resolved').filter(Q(closed_at=None) | ~Q(condition='recovered')).exists()
    assert not Case.objects.filter(first_seen_at__gt=F('last_seen_at')).exists()


def test_monitoring_reset_preserves_independent_sources():
    from monitoring.models import Source
    resource = Resource.objects.create(key='independent', name='Recurso conservado', kind='server')
    source = Source.objects.create(resource=resource, key='manual', name='Origen conservado')
    run('create_fake_monitoring', '--count', '3')
    call_command('delete_fake_data', '--confirm', stdout=StringIO())
    assert Source.objects.filter(pk=source.pk).exists()
    assert not Case.objects.exists()


@freeze_time('2026-11-06 12:00:00')
def test_secure_links_keep_all_lifecycle_states():
    run('create_fake_secure_links')
    assert {link.lifecycle_status for link in SecureLink.objects.all()} == set(SecureLink.LIFECYCLE_STATUSES)
    assert not SecureLink.objects.filter(origin='public', sent_at__isnull=False).exists()
    assert not SecureLink.objects.filter(project__isnull=False).exclude(client__user=F('project__client')).exists()


def test_secure_link_command_is_idempotent():
    run('create_fake_secure_links')
    before = (SecureLink.objects.count(), SecureLinkFolder.objects.count())
    run('create_fake_secure_links')
    assert (SecureLink.objects.count(), SecureLinkFolder.objects.count()) == before


def test_secure_link_reset_preserves_manual_links():
    run('create_fake_secure_links')
    link, _ = services.create_link(secret_type='custom', title='Manual conservado',
        fields={'custom_name': 'Nota', 'content': 'Texto ficticio independiente.'}, origin='panel')
    call_command('delete_fake_data', '--confirm', stdout=StringIO())
    assert list(SecureLink.objects.values_list('pk', flat=True)) == [link.pk]


def test_secure_link_replay_preserves_nonsecret_business_values():
    run('create_fake_secure_links')
    columns = ('title', 'origin', 'secret_type', 'client__user__username', 'project__name',
               'created_at', 'expires_at', 'consumed_at', 'revoked_at', 'sent_at')
    before = list(SecureLink.objects.order_by('title').values_list(*columns))
    call_command('delete_fake_data', '--confirm', stdout=StringIO())
    run('create_fake_secure_links')
    assert list(SecureLink.objects.order_by('title').values_list(*columns)) == before


def test_failed_file_reset_preserves_original_bytes(django_capture_on_commit_callbacks):
    run('seed_platform_data')
    resource = Deliverable.objects.exclude(file='').exclude(file=None).first()
    name, storage = resource.file.name, resource.file.storage
    with resource.file.open('rb') as original:
        before = original.read()
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError, match='late failure'):
            with fake_data_transaction():
                call_command('delete_fake_data', '--confirm', stdout=StringIO())
                raise RuntimeError('late failure')
    with storage.open(name, 'rb') as restored:
        assert restored.read() == before
    assert Deliverable.objects.filter(pk=resource.pk).exists()


def test_failed_seed_removes_new_files(django_capture_on_commit_callbacks):
    run('seed_platform_data')
    resource = Deliverable.objects.exclude(file='').exclude(file=None).first()
    storage = resource.file.storage
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError, match='late failure'):
            with fake_data_transaction():
                resource.file = sample_pdf('must-be-rolled-back.pdf')
                resource.save(update_fields=['file'])
                new_name = resource.file.name
                raise RuntimeError('late failure')
    assert not storage.exists(new_name)


def test_successful_reset_removes_obsolete_files(django_capture_on_commit_callbacks):
    run('seed_platform_data')
    resource = Deliverable.objects.exclude(file='').exclude(file=None).first()
    name, storage = resource.file.name, resource.file.storage
    with django_capture_on_commit_callbacks(execute=True):
        call_command('delete_fake_data', '--confirm', stdout=StringIO())
    assert not storage.exists(name)
