from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
import pytest

from content.models import FinancingAgreement


pytestmark = pytest.mark.django_db


def _seed_clients():
    call_command(
        'create_fake_clients_projects',
        '--count', '6',
        '--seed', '19',
        '--anchor-date', '2026-08-26',
        verbosity=0,
    )


def test_financing_seed_creates_representative_lifecycle(tmp_path, monkeypatch):
    """The financing fixture spans every state needed by the panel."""
    field = FinancingAgreement._meta.get_field('signed_document')
    monkeypatch.setattr(
        field,
        'storage',
        FileSystemStorage(location=tmp_path, base_url=None),
    )
    _seed_clients()

    call_command(
        'create_fake_financing',
        '--count', '5',
        '--seed', '19',
        '--anchor-date', '2026-08-26',
        verbosity=0,
    )

    statuses = set(FinancingAgreement.objects.values_list('status', flat=True))
    assert statuses == {'draft', 'ready', 'active', 'completed', 'cancelled'}
    assert FinancingAgreement.objects.filter(cycle_number=2).count() == 1
    assert FinancingAgreement.objects.filter(is_archived=True).count() == 1
    assert FinancingAgreement.objects.exclude(signed_document='').exclude(
        signed_document__isnull=True,
    ).count() == 3


def test_delete_fake_data_removes_private_financing_pdf(
    tmp_path, monkeypatch, django_capture_on_commit_callbacks,
):
    """Fixture cleanup retains private files until the deletion commits."""
    field = FinancingAgreement._meta.get_field('signed_document')
    monkeypatch.setattr(
        field,
        'storage',
        FileSystemStorage(location=tmp_path, base_url=None),
    )
    _seed_clients()
    call_command(
        'create_fake_financing',
        '--count', '3',
        '--seed', '19',
        '--anchor-date', '2026-08-26',
        verbosity=0,
    )
    signed_name = FinancingAgreement.objects.exclude(
        signed_document='',
    ).get().signed_document.name

    with django_capture_on_commit_callbacks(execute=True):
        call_command('delete_fake_data', '--confirm', verbosity=0)
        assert field.storage.exists(signed_name)

    assert not FinancingAgreement.objects.exists()
    assert not field.storage.exists(signed_name)


def test_delete_fake_data_removes_linked_financing_cycles(tmp_path, monkeypatch):
    """Fixture cleanup dissolves the protected link between financing cycles."""
    field = FinancingAgreement._meta.get_field('signed_document')
    monkeypatch.setattr(
        field,
        'storage',
        FileSystemStorage(location=tmp_path, base_url=None),
    )
    _seed_clients()
    call_command(
        'create_fake_financing',
        '--count', '4',
        '--seed', '19',
        '--anchor-date', '2026-08-26',
        verbosity=0,
    )
    assert FinancingAgreement.objects.filter(
        previous_agreement__isnull=False,
    ).exists()

    call_command('delete_fake_data', '--confirm', verbosity=0)

    assert not FinancingAgreement.objects.exists()


def test_financing_seed_builds_legal_snapshot_for_incomplete_client(
    make_client_profile,
):
    client = make_client_profile()

    call_command('create_fake_financing', '--count', '2', verbosity=0)

    ready = FinancingAgreement.objects.get(status='ready')
    assert ready.client_id_type == 'C.C.'
    assert ready.client_id_number == f'DEMO-{client.pk:06d}'
